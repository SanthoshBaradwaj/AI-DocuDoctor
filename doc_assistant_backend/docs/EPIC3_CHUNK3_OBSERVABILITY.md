# EPIC 3 Chunk #3: Observability + Debugging Runbook - Implementation Summary

## Status: ✅ COMPLETE

## Overview

This chunk ensures request_id propagation everywhere and adds structured logging with event names. It also adds a `/meta` endpoint for UI to display cost hints.

## Changes Made

### 1. Request ID Propagation

**Already Implemented:**
- `RequestIdMiddleware` in `app/main.py`:
  - Accepts `X-Request-Id` header from client
  - Auto-generates UUID4 if not provided
  - Stores in `request.state.request_id`
  - Adds to response header `X-Request-Id`
  - Sets in logging context

**Enhanced:**
- **OCR Service**: `HttpOcrService.extract_document()` now accepts `request_id` parameter
- **LLM Service**: `HttpLlmService.analyze_document()` already accepts `request_id` parameter
- **Forwarding**: Both services forward `request_id` as `X-Request-Id` header to upstream services
- **Document Storage**: `request_id` stored in `Document.request_id` field
- **Task Propagation**: Celery tasks read `request_id` from document

### 2. Structured Logging with Event Names

**Event Names Added:**

**Document Events:**
- `docs.notify` - Document upload notified
- `docs.get` - Get document request
- `docs.meta.get` - Get document metadata
- `docs.pagecount.start` - PDF page counting started
- `docs.pagecount.success` - Page count extracted successfully
- `docs.pagecount.limit_exceeded` - Page limit exceeded (hard stop)
- `docs.pagecount.fail` - Page counting failed (non-fatal)
- `docs.ocr.enqueued` - OCR task enqueued

**OCR Events:**
- `ocr.start` - OCR processing started
- `ocr.finish` - OCR processing completed successfully
- `ocr.fail` - OCR processing failed
- `ocr.text_read_success` - Text file read successfully
- `ocr.text_read_not_found` - Text file not found
- `ocr.text_read_failure` - Text file read failed
- `ocr.extraction_success` - OCR extraction completed
- `ocr.extraction_failure` - OCR extraction failed
- `ocr.update_failure` - Failed to update document after OCR
- `ocr.firestore_update` - Updating document in Firestore
- `ocr.llm_status_ready` - LLM status set to ready (chat available)

**LLM Events:**
- `llm.start` - LLM analysis started
- `llm.finish` - LLM analysis completed successfully
- `llm.fail` - LLM analysis failed
- `llm.text_prepared` - OCR text prepared for LLM (includes truncation info)
- `llm.text_fallback` - Using extracted text from extracted field
- `llm.not_ready` - Document not ready for LLM analysis
- `llm.validation_failure` - Document validation failed
- `llm.init_failure` - LLM initialization failed
- `llm.analysis_success` - LLM analysis completed
- `llm.analysis_failure` - LLM analysis failed
- `llm.update_failure` - Failed to update document after LLM
- `llm.firestore_update` - Updating document in Firestore

**Log Fields:**
All events include:
- `event`: Event name
- `request_id`: Request correlation ID
- `document_id`: Document ID (as string)
- `duration_ms`: Processing duration (where applicable)
- Relevant metadata (page_count, ocr_chars, llm_chars_sent, etc.)

### 3. Meta Endpoint (`app/api/v1/docs.py`)

**New Endpoint:**
- `GET /api/v1/docs/{doc_id}/meta`
- Returns: `DocMetaOut` with:
  - `id`, `filename`, `mime_type`, `size_bytes`
  - `domain`, `doc_type`
  - `page_count` (PDF pages)
  - `ocr_chars` (OCR text character count)
  - `llm_chars_sent` (Characters sent to LLM)

**Purpose:**
- UI can display cost hints
- Debugging: See what was sent to LLM
- Monitoring: Track processing costs

**Response Format:**
```json
{
  "id": "123",
  "filename": "document.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 1024000,
  "domain": "IDENTITY",
  "doc_type": "PASSPORT",
  "page_count": 5,
  "ocr_chars": 15000,
  "llm_chars_sent": 15000
}
```

### 4. Schema Updates (`app/schemas.py`)

**New Schema:**
- `DocMetaOut`: Metadata response model
- Includes all cost hint fields
- Used by `/meta` endpoint

## Request ID Flow

```
Client Request
  ↓ (X-Request-Id header or auto-generated)
RequestIdMiddleware
  ↓ (request.state.request_id)
API Endpoint (/notify, /chat, etc.)
  ↓ (stored in Document.request_id)
Database (Document.request_id field)
  ↓ (read by Celery task)
Background Task
  ↓ (passed to OCR/LLM services)
OCR/LLM Service
  ↓ (X-Request-Id header)
Upstream Service (gcp-ocr-service, gcp-llm-service)
  ↓ (logged with request_id)
Response
  ↓ (X-Request-Id header in response)
Client
```

## Structured Logging Examples

### Document Upload
```json
{
  "event": "docs.notify",
  "request_id": "req-123",
  "document_id": "456",
  "file_name": "document.pdf",
  "size_bytes": 1024000,
  "mime_type": "application/pdf"
}
```

### Page Count Success
```json
{
  "event": "docs.pagecount.success",
  "request_id": "req-123",
  "document_id": "456",
  "page_count": 5
}
```

### OCR Completion
```json
{
  "event": "ocr.finish",
  "request_id": "req-123",
  "document_id": "456",
  "ocr_chars": 15000,
  "text_length": 15000,
  "duration_ms": 523.45
}
```

### LLM Start
```json
{
  "event": "llm.start",
  "request_id": "req-123",
  "document_id": "456",
  "text_length": 15000,
  "sent_chars": 15000
}
```

## Files Changed

1. `app/api/v1/docs.py` - Added `/meta` endpoint, enhanced logging
2. `app/services/document_processor.py` - Enhanced logging with event names
3. `app/infrastructure/ai/base.py` - Added request_id to OCR service, enhanced logging
4. `app/schemas.py` - Added `DocMetaOut` schema
5. `app/main.py` - RequestIdMiddleware already handles X-Request-Id header

## Backward Compatibility

✅ **Maintained:**
- All existing endpoints unchanged
- New `/meta` endpoint is additive
- Request ID is optional (auto-generated if not provided)
- Event names are additive (existing logs still work)

## Next Steps

- Chunk #4: Tests
- Documentation: Runbook with PowerShell scripts
