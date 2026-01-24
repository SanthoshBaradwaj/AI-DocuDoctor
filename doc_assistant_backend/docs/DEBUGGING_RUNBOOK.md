# Debugging Runbook: How to Debug with request_id

## Overview

This document explains how to use `request_id` to debug issues in the AI-DocuDoctor backend, from API requests through to background tasks and upstream service calls.

## Request ID Propagation

### End-to-End Flow

```
Client Request
  ↓ (X-Request-Id header or auto-generated)
FastAPI Middleware
  ↓ (request.state.request_id)
API Endpoint
  ↓ (logged with request_id)
Database (Document.request_id field)
  ↓ (stored in document)
Celery Task
  ↓ (logged with request_id from document)
Upstream Service (X-Request-Id header)
  ↓ (logged with request_id)
Response
  ↓ (X-Request-Id header in response)
Client
```

### Request ID Sources

1. **Client-provided**: Client can send `X-Request-Id` header
2. **Auto-generated**: If not provided, backend generates UUID4
3. **Document storage**: Request ID is stored in `Document.request_id` field
4. **Task propagation**: Celery tasks read `request_id` from document

## How to Debug with request_id

### Step 1: Get request_id from Error Response

When an error occurs, the response includes `request_id`:

```json
{
  "error_code": "LLM_TIMEOUT",
  "message": "LLM service timed out",
  "details": {"doc_id": "123"},
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Step 2: Search Logs by request_id

#### Using gcloud (Cloud Run)

```powershell
# Search logs for a specific request_id
gcloud logging read "jsonPayload.request_id=`"550e8400-e29b-41d4-a716-446655440000`"" --limit 100 --format json

# Search with time range (last hour)
gcloud logging read "jsonPayload.request_id=`"550e8400-e29b-41d4-a716-446655440000`"" --limit 100 --format json --freshness=1h

# Search across all log levels
gcloud logging read "jsonPayload.request_id=`"550e8400-e29b-41d4-a716-446655440000`"" --limit 100 --format json --severity=DEBUG,INFO,WARNING,ERROR
```

#### Using PowerShell Script

```powershell
# Use the fetch_logs.ps1 script (see scripts/fetch_logs.ps1)
.\scripts\fetch_logs.ps1 -RequestId "550e8400-e29b-41d4-a716-446655440000"
```

#### Using Local Logs (Docker)

```powershell
# If running locally with Docker
docker-compose logs api | Select-String "550e8400-e29b-41d4-a716-446655440000"
docker-compose logs worker | Select-String "550e8400-e29b-41d4-a716-446655440000"
```

### Step 3: Trace Request Flow

1. **API Request**: Look for `event=chat.request.started` or `event=docs.notify.started`
2. **Database Operations**: Look for `event=document.created` or `event=document.updated`
3. **Background Tasks**: Look for `event=ocr.started`, `event=llm.started`
4. **Upstream Calls**: Look for `event=llm.chat.success` or `event=llm.chat.fail`
5. **Response**: Look for `event=chat.request.completed` or final status

### Step 4: Identify Issues

Common patterns to look for:

- **Timeout**: `error_type=LLM_TIMEOUT`, `duration_ms` > 20000
- **Connection Error**: `error_type=LLM_UNREACHABLE`
- **Upstream Error**: `upstream_status_code=502`, `upstream_error_code=...`
- **Validation Error**: `error_code=VALIDATION_ERROR`

## Status Interpretation Guide

### Document Status Fields

#### `status` (Legacy)
- `"processing"`: Document is being processed (OCR or LLM)
- `"ready"`: Document is ready (OCR completed)
- `"error"`: Processing failed

#### `ocr_status` (Pipeline Step)
- `"pending"`: OCR not started
- `"processing"`: OCR in progress
- `"ready"`: OCR completed, text extracted
- `"error"`: OCR failed

#### `llm_status` (Pipeline Step / Chat Availability)
- `"pending"`: Chat not available (OCR not ready)
- `"ready"`: **Chat available** (OCR completed) OR LLM analysis complete
- `"processing"`: LLM analysis in progress
- `"error"`: LLM analysis failed

### Status Semantics (Updated)

**Key Change**: `llm_status="ready"` now means "chat available", not just "LLM analysis complete".

**State Transitions**:
1. Document created → `ocr_status="pending"`, `llm_status="pending"`
2. OCR starts → `ocr_status="processing"`, `llm_status="pending"`
3. OCR completes → `ocr_status="ready"`, `llm_status="ready"` ✅ **Chat now available**
4. LLM analysis starts → `ocr_status="ready"`, `llm_status="processing"`
5. LLM analysis completes → `ocr_status="ready"`, `llm_status="ready"`

### UI Interpretation

**When to enable chat**:
- ✅ `ocr_status="ready"` AND `llm_status="ready"` → Chat enabled
- ✅ `ocr_status="ready"` AND `llm_status="processing"` → Chat enabled (analysis in progress)
- ❌ `ocr_status="pending"` OR `ocr_status="processing"` → Chat disabled
- ❌ `ocr_status="error"` → Chat disabled, show error

**Status Display**:
- Show spinner: `ocr_status="processing"` OR `llm_status="processing"`
- Show ready: `ocr_status="ready"` AND `llm_status="ready"`
- Show error: `ocr_status="error"` OR `llm_status="error"`

## Example Debugging Session

### Scenario: Chat endpoint returns 504 timeout

1. **Get request_id from error**:
   ```json
   {
     "error_code": "LLM_TIMEOUT",
     "request_id": "req-123-abc"
   }
   ```

2. **Search logs**:
   ```powershell
   gcloud logging read "jsonPayload.request_id=`"req-123-abc`"" --limit 50
   ```

3. **Trace flow**:
   - `event=chat.request.started` → Request received
   - `event=llm.chat.started` → LLM call started
   - `event=llm.chat.fail`, `error_type=TimeoutError` → LLM timed out
   - `event=chat.request.fail` → Error returned to client

4. **Check upstream**:
   - Look for `upstream_status_code`, `duration_ms`
   - Check if LLM service `/health` is responding
   - Verify `LLM_SERVICE_URL` is correct

5. **Verify request_id propagation**:
   - Check if `X-Request-Id` header was sent to LLM service
   - Verify LLM service logs include the same request_id

## PowerShell Scripts

See `scripts/` directory for:
- `fetch_logs.ps1`: Fetch logs by request_id
- `upload.ps1`: Upload document and get request_id
- `poll_status.ps1`: Poll document status
- `chat.ps1`: Send chat request and capture request_id

## Best Practices

1. **Always log request_id**: Include in all log statements
2. **Forward request_id**: Send `X-Request-Id` header to upstream services
3. **Store in database**: Save request_id in Document for traceability
4. **Return in errors**: Always include request_id in error responses
5. **Use structured logs**: JSON format makes searching easier

## Troubleshooting

### request_id not in logs
- Check if middleware is registered
- Verify logging formatter includes request_id
- Check if request_id is set in request.state

### request_id not propagated to tasks
- Verify Document.request_id is set during creation
- Check if Celery task reads request_id from document
- Ensure task logs include request_id

### Cannot find logs
- Verify time range (logs may be older than retention)
- Check log level (DEBUG logs may be filtered)
- Verify service name in gcloud command
