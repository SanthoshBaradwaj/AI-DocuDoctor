# EPIC 3: MVP Hardening + Cost Guardrails + Reliability - Implementation Summary

## Status: ✅ COMPLETE

## Overview

EPIC 3 implements cost guardrails to prevent runaway OCR/LLM costs, improves observability with structured logging and request_id propagation, and adds a meta endpoint for UI cost hints.

## Implementation Summary

### CHUNK 1: Page Count + Limits ✅

**Goal:** Hard stop BEFORE OCR to prevent processing large PDFs.

**Implemented:**
- ✅ Config vars: `MAX_UPLOAD_BYTES` (15MB), `MAX_PDF_PAGES` (10), `MAX_IMAGES` (20), `MAX_OCR_CHARS` (50000)
- ✅ PDF page counting in `/notify` endpoint using `pypdf`
- ✅ Hard stop: If `page_count > MAX_PDF_PAGES`, return HTTP 413 with `PAGE_LIMIT_EXCEEDED`
- ✅ File size enforcement in both `/presign` and `/notify`
- ✅ Cost hints stored: `page_count` in document record
- ✅ Structured logging: `docs.notify`, `docs.pagecount.*` events

**Files Changed:**
- `app/core/config.py` - Added limit config vars
- `app/infrastructure/db/models.py` - Added `page_count`, `ocr_chars`, `llm_chars_sent`
- `app/services/pdf_utils.py` - NEW: PDF page counting utility
- `app/infrastructure/storage/` - Added `read_bytes()` method
- `app/api/v1/docs.py` - Enhanced presign and notify with limits
- `app/infrastructure/db/firestore_adapter.py` - Support for new fields
- `requirements.txt` - Added `pypdf==5.1.0`

### CHUNK 2: OCR/LLM Cost Safety ✅

**Goal:** Truncate OCR text before sending to LLM to cap costs.

**Implemented:**
- ✅ OCR text truncation: Only send first `MAX_OCR_CHARS` to LLM
- ✅ Full text preserved: Complete OCR text stored in `doc.body`
- ✅ Cost hints stored: `ocr_chars`, `llm_chars_sent` in document record
- ✅ Structured logging: `llm.text_prepared`, `llm.start`, `llm.finish` with truncation info

**Files Changed:**
- `app/services/document_processor.py` - Added text truncation before LLM
- `app/infrastructure/db/models.py` - Added cost hint fields (from Chunk 1)

### CHUNK 3: Observability + Debugging ✅

**Goal:** Ensure request_id propagation everywhere and add structured logging.

**Implemented:**
- ✅ Request ID propagation: `X-Request-Id` header accepted and forwarded to OCR/LLM services
- ✅ Structured logging: Event names added (`docs.*`, `ocr.*`, `llm.*`)
- ✅ Meta endpoint: `GET /api/v1/docs/{doc_id}/meta` returns cost hints
- ✅ All logs include `request_id`, `document_id`, event names

**Files Changed:**
- `app/api/v1/docs.py` - Added `/meta` endpoint, enhanced logging
- `app/services/document_processor.py` - Enhanced logging with event names
- `app/infrastructure/ai/base.py` - Added request_id to OCR service, enhanced logging
- `app/schemas.py` - Added `DocMetaOut` schema
- `app/main.py` - RequestIdMiddleware already handles X-Request-Id header

### CHUNK 4: Tests + Documentation ✅

**Implemented:**
- ✅ Unit tests: `tests/test_epic3_chunk1_page_limits.py`
- ✅ Documentation: `docs/EPIC3_CHUNK1_PAGE_LIMITS.md`, `EPIC3_CHUNK2_OCR_LLM_GUARDRAILS.md`, `EPIC3_CHUNK3_OBSERVABILITY.md`, `EPIC3_RUNBOOK.md`
- ✅ PowerShell scripts: `scripts/check_meta.ps1`, `scripts/upload_and_verify_limits.ps1`

## Acceptance Criteria Verification

✅ **All Criteria Met:**

1. ✅ Upload PDF with pages <= MAX_PDF_PAGES succeeds and proceeds to OCR
2. ✅ Upload PDF with pages > MAX_PDF_PAGES fails immediately with HTTP 413 and `PAGE_LIMIT_EXCEEDED`
3. ✅ LLM request never receives > MAX_OCR_CHARS text
4. ✅ `GET /api/v1/docs/{doc_id}/meta` returns `page_count` and char counters
5. ✅ All new tests pass

## Error Response Format

All errors use normalized envelope:
```json
{
  "error_code": "PAGE_LIMIT_EXCEEDED",
  "message": "PDF has 15 pages, max allowed is 10",
  "details": {
    "page_count": 15,
    "max_pages": 10,
    "doc_id": "123"
  },
  "request_id": "req-456"
}
```

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
- All limits have safe defaults
- No manual config required to run locally

## Backward Compatibility

✅ **Maintained:**
- All existing API routes unchanged
- All existing JSON response shapes unchanged
- New fields (`page_count`, `ocr_chars`, `llm_chars_sent`) are optional/nullable
- Documents without cost hints still work
- Non-PDF files skip page counting
- Request ID is optional (auto-generated if not provided)

## Structured Logging

**Event Names:**
- `docs.notify` - Document upload notified
- `docs.pagecount.*` - PDF page counting events
- `docs.ocr.enqueued` - OCR task enqueued
- `ocr.start/finish/fail` - OCR processing events
- `llm.start/finish/fail` - LLM processing events

**All events include:**
- `event`: Event name
- `request_id`: Request correlation ID
- `document_id`: Document ID (as string)
- Relevant metadata (page_count, ocr_chars, llm_chars_sent, etc.)

## Request ID Flow

```
Client Request (X-Request-Id header)
  ↓
RequestIdMiddleware (auto-generate if missing)
  ↓
API Endpoint (store in Document.request_id)
  ↓
Database (Document.request_id field)
  ↓
Background Task (read from document)
  ↓
OCR/LLM Service (forward as X-Request-Id header)
  ↓
Upstream Service (logged with request_id)
  ↓
Response (X-Request-Id header)
```

## Files Changed Summary

**New Files:**
- `app/services/pdf_utils.py` - PDF page counting utility
- `tests/test_epic3_chunk1_page_limits.py` - Unit tests
- `docs/EPIC3_CHUNK1_PAGE_LIMITS.md` - Chunk 1 documentation
- `docs/EPIC3_CHUNK2_OCR_LLM_GUARDRAILS.md` - Chunk 2 documentation
- `docs/EPIC3_CHUNK3_OBSERVABILITY.md` - Chunk 3 documentation
- `docs/EPIC3_RUNBOOK.md` - Verification runbook
- `scripts/check_meta.ps1` - Meta endpoint verification script
- `scripts/upload_and_verify_limits.ps1` - Upload and limits verification script

**Modified Files:**
- `app/core/config.py` - Added limit config vars
- `app/infrastructure/db/models.py` - Added cost hint fields
- `app/infrastructure/storage/base.py` - Added `read_bytes()` protocol
- `app/infrastructure/storage/gcs_backend.py` - Implemented `read_bytes()`
- `app/infrastructure/storage/storage_factory.py` - Implemented `read_bytes()` for S3
- `app/api/v1/docs.py` - Enhanced presign/notify, added `/meta` endpoint
- `app/services/document_processor.py` - Added text truncation, enhanced logging
- `app/infrastructure/ai/base.py` - Added request_id to OCR, enhanced logging
- `app/infrastructure/db/firestore_adapter.py` - Support for new fields
- `app/schemas.py` - Added `DocMetaOut` schema
- `requirements.txt` - Added `pypdf==5.1.0`

## Next Steps

1. **Deploy to Cloud Run:**
   - Set environment variables for limits
   - Deploy backend with new code
   - Verify using PowerShell scripts

2. **Monitor:**
   - Check logs for structured events
   - Verify request_id propagation
   - Monitor cost hints via `/meta` endpoint

3. **Future Enhancements:**
   - Add rate limiting (per-IP)
   - Add quotas (max messages, max docs per user)
   - Add streaming support for chat
   - Add cost analytics dashboard

## Verification

Use the PowerShell scripts in `scripts/` to verify:
- Page limit enforcement
- File size limit enforcement
- Meta endpoint functionality
- Request ID propagation
- OCR text truncation

See `docs/EPIC3_RUNBOOK.md` for detailed verification commands.
