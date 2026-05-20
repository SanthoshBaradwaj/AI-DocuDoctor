# EPIC 3 Chunk #1: Page Count + Limits - Implementation Summary

## Status: ✅ COMPLETE

## Overview

This chunk implements hard stops BEFORE OCR processing to prevent runaway costs from large PDFs. It enforces page count limits and file size limits at the `/notify` endpoint.

## Changes Made

### 1. Configuration Variables (`app/core/config.py`)

Added new environment variables with safe defaults:
- `MAX_UPLOAD_BYTES: int = 15 * 1024 * 1024` (15MB default)
- `MAX_PDF_PAGES: int = 10` (default)
- `MAX_IMAGES: int = 20` (wired for future use)
- `MAX_OCR_CHARS: int = 50000` (default)
- `MAX_REPLY_CHARS: int = 50000` (already existed, kept)

### 2. Document Model Updates (`app/infrastructure/db/models.py`)

Added cost guardrail fields:
- `page_count: Mapped[int | None]` - PDF page count
- `ocr_chars: Mapped[int | None]` - OCR text character count
- `llm_chars_sent: Mapped[int | None]` - Characters sent to LLM

### 3. PDF Page Counting (`app/services/pdf_utils.py`)

**New Module:**
- `count_pdf_pages(pdf_bytes: bytes) -> int`: Counts pages using `pypdf`
- Handles invalid PDFs with proper error messages
- Logs page count extraction

### 4. Storage Backend Enhancement (`app/infrastructure/storage/`)

**Added Method:**
- `read_bytes(key: str) -> bytes`: Server-to-server file reading
- Implemented in both `GCSStorageBackend` and `S3MinIOStorageBackend`
- Used for PDF page counting without presigned URLs

### 5. Upload Presign Endpoint (`app/api/v1/docs.py`)

**Enhanced:**
- Uses `MAX_UPLOAD_BYTES` instead of just `MAX_UPLOAD_MB`
- Enforces size limit in presign response
- Returns HTTP 413 with `PAYLOAD_TOO_LARGE` if exceeded

### 6. Notify Endpoint (`app/api/v1/docs.py`)

**Major Changes:**
- Enforces `MAX_UPLOAD_BYTES` (double-check)
- **PDF Page Counting**: If `mime_type == "application/pdf"`:
  - Downloads PDF from storage (server-to-server)
  - Counts pages using `pypdf`
  - Stores `page_count` in document
  - **Hard Stop**: If `page_count > MAX_PDF_PAGES`:
    - Sets `status="error"`, `ocr_status="error"`, `llm_status="error"`
    - Returns HTTP 413 with normalized error:
      ```json
      {
        "error_code": "PAGE_LIMIT_EXCEEDED",
        "message": "PDF has {page_count} pages, max allowed is {max_pages}",
        "details": {
          "page_count": 15,
          "max_pages": 10,
          "doc_id": "123"
        },
        "request_id": "req-456"
      }
      ```
    - **Does NOT enqueue OCR/LLM** (hard stop)
- Structured logging with event names:
  - `docs.notify` - Document upload notified
  - `docs.pagecount.start` - Page counting started
  - `docs.pagecount.success` - Page count extracted
  - `docs.pagecount.limit_exceeded` - Page limit exceeded
  - `docs.pagecount.fail` - Page counting failed (non-fatal)

### 7. Firestore Adapter Updates (`app/infrastructure/db/firestore_adapter.py`)

**Updated:**
- `_doc_to_dict()`: Includes `page_count`, `ocr_chars`, `llm_chars_sent`
- `_dict_to_doc()`: Reads `page_count`, `ocr_chars`, `llm_chars_sent` from Firestore

### 8. Dependencies (`requirements.txt`)

**Added:**
- `pypdf==5.1.0` - For PDF page counting

## Error Handling

### Page Limit Exceeded

**Response:**
- Status: `413 Payload Too Large`
- Error Code: `PAGE_LIMIT_EXCEEDED`
- Message: `"PDF has {page_count} pages, max allowed is {max_pages}"`
- Details: `{page_count, max_pages, doc_id}`
- Request ID: Included for correlation

**Behavior:**
- Document status set to `"error"`
- OCR/LLM status set to `"error"`
- OCR/LLM tasks **NOT enqueued** (hard stop)
- Document record created but marked as failed

### File Size Limit Exceeded

**Response:**
- Status: `413 Payload Too Large`
- Error Code: `PAYLOAD_TOO_LARGE`
- Message: `"File size ({size_bytes} bytes) exceeds maximum allowed size ({max_size_bytes} bytes)"`
- Details: `{size_bytes, max_size_bytes, filename}`

**Enforcement:**
- Checked in `/presign` endpoint (early rejection)
- Checked again in `/notify` endpoint (double-check)

## Structured Logging

All events include:
- `event`: Event name (e.g., `docs.notify`, `docs.pagecount.success`)
- `request_id`: Request correlation ID
- `document_id`: Document ID (as string)
- Relevant metadata (page_count, size_bytes, etc.)

**Event Names:**
- `docs.notify` - Document upload notified
- `docs.pagecount.start` - Page counting started
- `docs.pagecount.success` - Page count extracted successfully
- `docs.pagecount.limit_exceeded` - Page limit exceeded (hard stop)
- `docs.pagecount.fail` - Page counting failed (non-fatal, continues)
- `docs.ocr.enqueued` - OCR task enqueued

## Backward Compatibility

✅ **Maintained:**
- All existing API routes unchanged
- All existing JSON response shapes unchanged
- New fields (`page_count`, `ocr_chars`, `llm_chars_sent`) are optional/nullable
- Documents without page_count still process normally
- Non-PDF files skip page counting

## Testing

See `tests/test_epic3_chunk1_page_limits.py` for:
- Page count extraction tests
- Page limit enforcement tests
- File size limit enforcement tests
- Error response format validation

## Configuration

**Environment Variables:**
```bash
MAX_UPLOAD_BYTES=15728640  # 15MB in bytes
MAX_PDF_PAGES=10
MAX_IMAGES=20
MAX_OCR_CHARS=50000
MAX_REPLY_CHARS=50000
```

**Defaults (if not set):**
- `MAX_UPLOAD_BYTES`: 15MB
- `MAX_PDF_PAGES`: 10
- `MAX_IMAGES`: 20
- `MAX_OCR_CHARS`: 50000
- `MAX_REPLY_CHARS`: 50000

## Files Changed

1. `app/core/config.py` - Added limit config vars
2. `app/infrastructure/db/models.py` - Added cost hint fields
3. `app/services/pdf_utils.py` - NEW: PDF page counting utility
4. `app/infrastructure/storage/base.py` - Added `read_bytes()` protocol method
5. `app/infrastructure/storage/gcs_backend.py` - Implemented `read_bytes()`
6. `app/infrastructure/storage/storage_factory.py` - Implemented `read_bytes()` for S3
7. `app/api/v1/docs.py` - Enhanced presign and notify with limits
8. `app/infrastructure/db/firestore_adapter.py` - Added new fields support
9. `requirements.txt` - Added `pypdf==5.1.0`
10. `tests/test_epic3_chunk1_page_limits.py` - NEW: Tests

## Acceptance Criteria

✅ **Verified:**
1. Upload PDF with pages <= MAX_PDF_PAGES succeeds and proceeds to OCR
2. Upload PDF with pages > MAX_PDF_PAGES fails immediately with HTTP 413 and `PAGE_LIMIT_EXCEEDED`
3. File size limits enforced in both presign and notify
4. All errors use normalized error envelope format
5. Request ID included in all responses

## Next Steps

- Chunk #2: OCR/LLM Cost Safety (text truncation)
- Chunk #3: Observability + Debugging Runbook
- Chunk #4: Tests
