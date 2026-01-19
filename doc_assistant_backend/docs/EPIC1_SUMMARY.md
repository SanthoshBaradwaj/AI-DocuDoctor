# EPIC 1 Summary: True Upload Pipeline with OCR

## Overview

EPIC 1 focuses on implementing a working async document processing pipeline that uses the OCR service abstraction to extract text from uploaded documents. The pipeline flows from upload notification through Celery task queue to database updates, with proper status tracking and structured logging.

## CHUNK1: True Upload Pipeline with Fake OCR (End-to-End)

### Goal

Make the async pipeline actually do work using the existing FakeOcrService, so that:
- `/api/v1/docs/upload/presign` + client upload + `/api/v1/docs/notify` triggers `process_document_ocr` via TaskQueue
- Updates the Document row with real-looking text/excerpt/extracted
- Moves status from "processing" to "ready" or "error"

### OcrResult Model

A new Pydantic model was introduced to structure OCR extraction results:

```python
class OcrResult(BaseModel):
    text: str
    page_count: Optional[int] = None
    language: Optional[str] = None
```

This model provides a consistent interface for OCR results across different implementations (fake, Gemini Vision, AWS Textract, etc.).

### OcrService Protocol Update

The `OcrService` Protocol was updated to use a storage-key-based interface:

```python
def extract_document(
    self,
    *,
    storage_key: str,
    mime_type: Optional[str] = None,
) -> OcrResult:
```

This allows the OCR service to work directly with storage keys, abstracting away the need for the caller to download files first. The service implementation handles storage access internally.

### FakeOcrService Implementation

The `FakeOcrService` was updated to implement `extract_document()`:

- **For text files**: Attempts to read actual content from MinIO storage
- **For other files**: Generates deterministic fake text based on storage key
- **Returns**: `OcrResult` with:
  - `text`: Extracted or fake text content
  - `page_count`: Always 1 for fake implementation
  - `language`: Always "en" for fake implementation

This provides a working implementation for local development without requiring external OCR APIs.

### Pipeline Flow

The complete upload and processing pipeline now works as follows:

1. **Client calls** `POST /api/v1/docs/upload/presign`
   - Backend generates presigned upload URL
   - Returns `storage_key`, `upload_url`, `upload_fields`

2. **Client uploads file** directly to MinIO using presigned URL

3. **Client calls** `POST /api/v1/docs/notify`
   - Backend creates Document record with `status="processing"`
   - Enqueues OCR task via `TaskQueue.enqueue_ocr(document_id)`
   - Returns Document details immediately

4. **Celery worker** picks up task and calls `process_document_ocr(document_id)`
   - Loads document from database
   - Sets status to "processing" if not already
   - Calls `get_ocr_service().extract_document(storage_key, mime_type)`
   - Updates document:
     - `body` = OCR result text
     - `excerpt` = First 300 characters (cut at word boundary)
     - `extracted` = JSON with `page_count` and `language`
   - Sets status to "ready"
   - Commits changes

5. **Client can poll** `GET /api/v1/docs/{doc_id}` to see status progression:
   - Initially: `status="processing"`
   - After OCR: `status="ready"` with populated `body`, `excerpt`, `extracted`

### Status Values

The system uses consistent status values defined in `DocumentStatus`:
- `"uploaded"` - Document uploaded but not yet processed
- `"processing"` - OCR/extraction in progress
- `"ready"` - Processing complete, document ready for use
- `"error"` - Processing failed

### Error Handling

The Celery task includes comprehensive error handling:
- **Document not found**: Logs warning and returns early
- **Storage download failure**: Sets status to "error", logs error with stack trace
- **OCR service failure**: Catches exception, sets status to "error", logs with full context
- **Database errors**: Handled in finally block to ensure session cleanup

All errors are logged with structured fields including `document_id`, `error`, and `exc_info=True` for stack traces.

### Logging

Structured logging is used throughout the pipeline:

**In `/api/v1/docs/notify`:**
- "Document upload notified, enqueuing OCR" with `document_id`, `domain`, `doc_type`, `file_name`, `storage_key`
- "OCR task enqueued via TaskQueue" with `task_id`, `queue_backend`

**In `process_document_ocr` Celery task:**
- "Starting OCR processing" with `document_id`, `current_status`, `domain`, `doc_type`, `queue_backend`
- "OCR processing completed successfully" with `document_id`, `status`, `page_count`, `language`, `domain`, `doc_type`
- Error logs include full exception context

### Key Changes

1. **`app/infrastructure/ai/base.py`**:
   - Added `OcrResult` Pydantic model
   - Updated `OcrService` Protocol to `extract_document(storage_key, mime_type) -> OcrResult`
   - Updated `FakeOcrService` to implement new interface

2. **`app/infrastructure/queue/celery_queue.py`**:
   - Removed direct dependency on `naive_extract_from_minio` and `build_extracted`
   - Now uses `get_ocr_service().extract_document()` abstraction
   - Updates document with OCR results (text, excerpt, extracted metadata)
   - Improved logging with page_count and language

3. **No changes to API contracts**: All existing endpoints and schemas remain unchanged, ensuring backward compatibility.

### Testing

The pipeline can be tested end-to-end:

1. Start services: `docker compose up`
2. Upload a document via Flutter app or PowerShell script
3. Check document status: `GET /api/v1/docs/{doc_id}`
   - Initially shows `status="processing"`
   - After a few seconds, shows `status="ready"` with populated `body` and `excerpt`
4. Check worker logs: `docker compose logs worker`
   - Should show "Starting OCR processing" and "OCR processing completed successfully"

### CHUNK2: Real HTTP OCR Service

### Goal

Introduce a real HTTP-based OCR backend as an `HttpOcrService`, selected via configuration, without changing the public HTTP API or Celery task contracts. The only caller of OCR remains the `OcrService` abstraction.

### OCR Provider Configuration

Two OCR provider modes are now supported:

1. **`fake`** (default): Uses `FakeOcrService` for local development
   - Generates deterministic fake text based on storage key
   - For `.txt` files, reads actual content from MinIO storage
   - Returns `OcrResult` with `page_count=1` and `language="en"`

2. **`http`**: Uses `HttpOcrService` to call an external OCR microservice
   - Calls HTTP endpoint at `OCR_SERVICE_URL/extract`
   - Sends `storage_key` and optional `mime_type` in JSON payload
   - Expects response with `text`, `page_count`, and `language` fields
   - Maps response to `OcrResult` model

### Configuration

New environment variables:

- **`OCR_PROVIDER`**: Provider selection (`"fake"` or `"http"`, default: `"fake"`)
- **`OCR_SERVICE_URL`**: Base URL for HTTP OCR service (required when `OCR_PROVIDER="http"`)
  - Example: `"http://ocr-service:8080"` or `"https://ocr.example.com"`

### HttpOcrService Implementation

The `HttpOcrService` class:

- **Initialization**: Takes `base_url` and optional `http_client` (httpx.Client)
- **Extract Method**: 
  - POSTs to `{base_url}/extract` with JSON payload
  - Handles HTTP errors (status codes, network errors)
  - Validates response format and maps to `OcrResult`
  - Logs metadata only (not full document text)
- **Error Handling**:
  - `httpx.HTTPStatusError` for HTTP status errors
  - `httpx.RequestError` for network/timeout errors
  - `ValueError` for invalid response format

### Factory Function

The `get_ocr_service()` factory function:

- Reads `OCR_PROVIDER` from settings
- Returns `FakeOcrService()` when `OCR_PROVIDER="fake"`
- Returns `HttpOcrService(base_url=settings.OCR_SERVICE_URL)` when `OCR_PROVIDER="http"`
- Raises `ValueError` if:
  - `OCR_PROVIDER="http"` but `OCR_SERVICE_URL` is not set
  - `OCR_PROVIDER` has an unsupported value

### HTTP OCR Service Contract

The external OCR microservice should:

- **Endpoint**: `POST /extract`
- **Request Body**:
  ```json
  {
    "storage_key": "user_1/uuid/document.pdf",
    "mime_type": "application/pdf"  // optional
  }
  ```
- **Response** (200 OK):
  ```json
  {
    "text": "Extracted text content...",
    "page_count": 3,  // optional
    "language": "en"  // optional
  }
  ```

### Running Locally

**With Fake OCR (default):**
```bash
export OCR_PROVIDER=fake
docker compose up
```

**With HTTP OCR Service:**
```bash
export OCR_PROVIDER=http
export OCR_SERVICE_URL=http://ocr-service:8080
docker compose up
```

Or in `docker-compose.yml`:
```yaml
environment:
  - OCR_PROVIDER=http
  - OCR_SERVICE_URL=http://ocr-service:8080
```

### Testing

Unit tests cover:

- `FakeOcrService`: Returns correct `OcrResult` format
- `HttpOcrService`: 
  - Successful extraction with valid response
  - HTTP error handling
  - Invalid response format handling
  - Missing required fields handling
- `get_ocr_service()` factory:
  - Returns correct service based on `OCR_PROVIDER`
  - Error handling for missing/invalid configuration

### Key Changes

1. **`app/core/config.py`**:
   - Added `OCR_PROVIDER: Literal["fake", "http"] = "fake"`
   - Added `OCR_SERVICE_URL: Optional[str] = None`

2. **`app/infrastructure/ai/base.py`**:
   - Added `HttpOcrService` class implementing `OcrService` Protocol
   - Updated `get_ocr_service()` to use `OCR_PROVIDER` setting
   - Added httpx dependency for HTTP client

3. **`requirements.txt`**:
   - Added `httpx==0.27.0` for HTTP client
   - Added `pytest==8.3.3` and `pytest-mock==3.14.0` for testing

4. **`docker-compose.yml`**:
   - Added `OCR_PROVIDER=fake` and `OCR_SERVICE_URL=` to api and worker services

5. **`tests/test_ocr_service.py`** (new):
   - Comprehensive unit tests for all OCR service implementations
   - Tests for factory function with different configurations

### Backward Compatibility

- Default behavior unchanged: `OCR_PROVIDER` defaults to `"fake"`
- No changes to API contracts or Celery task signatures
- Existing code using `get_ocr_service()` continues to work without modification

## CHUNK3: LLM Abstraction and Async Analysis Pipeline

### Goal

Introduce a `LlmService` + `LlmResult` abstraction (similar to `OcrService` + `OcrResult`), implement `FakeLlmService`, and add a Celery task that runs LLM analysis on OCR'd text. Refactor legacy `/analyze` code to reuse this abstraction and the same output fields, without breaking external API contracts.

### LlmResult Model

A new Pydantic model was introduced to structure LLM analysis results:

```python
class LlmResult(BaseModel):
    summary: str
    entities: list[dict] = []  # List of entity dicts
```

This model provides a consistent interface for LLM results across different implementations (fake, Gemini, OpenAI, Anthropic, etc.).

### LlmService Protocol

The `LLMService` Protocol was extended to include document analysis:

```python
def analyze_document(
    self,
    *,
    text: str,
    mime_type: Optional[str] = None,
    doc_type: Optional[str] = None,
) -> LlmResult:
```

This allows the LLM service to analyze document text and extract summary and entities, separate from the chat/conversation `generate()` method.

### FakeLlmService Implementation

The `FakeLlmService` was updated to implement `analyze_document()`:

- **Summary Generation**: 
  - Truncates text to 240 characters (matching legacy `summarize()` behavior)
  - Adds "[fake summary]" suffix
  - Handles empty text gracefully

- **Entity Generation**:
  - Always includes `TOKEN_COUNT` entity (matching legacy `fake_ner()` behavior)
  - Includes `DOC_TYPE` entity if `doc_type` is provided
  - Includes generic `FAKE_TAG` entity

- **Deterministic**: Produces consistent results based on input text

### Pipeline Flow

The complete document processing pipeline now works as follows:

1. **Client calls** `POST /api/v1/docs/notify`
   - Backend creates Document record with `status="processing"`
   - Enqueues OCR task

2. **Celery worker** runs `process_document_ocr(document_id)`
   - Extracts text via OCR service
   - Updates document: `body`, `excerpt`, `extracted` (OCR metadata)
   - Sets status to "ready"
   - **Automatically enqueues LLM analysis task**

3. **Celery worker** runs `process_document_llm(document_id)`
   - Verifies document has `body` and `status="ready"`
   - Calls `get_llm_service().analyze_document(text, mime_type, doc_type)`
   - Updates document: `extracted` field with `summary` and `entities`
   - Keeps status as "ready" (doesn't change status on LLM failure)

4. **Client can poll** `GET /api/v1/docs/{doc_id}` to see:
   - `status="ready"` after OCR
   - `extracted` field populated with `summary` and `entities` after LLM analysis

### Legacy /analyze Endpoint Refactoring

The `/analyze` and `/analyze/batch` endpoints were refactored to:

- Use `get_llm_service().analyze_document()` instead of direct `build_extracted()` calls
- Maintain the same response shape and field names (`extracted.summary`, `extracted.entities`)
- Preserve backward compatibility for existing clients

**Before:**
```python
from app.services.extract import build_extracted
doc.extracted = build_extracted(doc.body)
```

**After:**
```python
from app.infrastructure.ai.base import get_llm_service
llm_service = get_llm_service()
llm_result = llm_service.analyze_document(text=doc.body, mime_type=doc.mime, doc_type=doc.doc_type)
doc.extracted = {
    "summary": llm_result.summary,
    "entities": llm_result.entities,
}
```

### Error Handling

The `process_document_llm` task includes comprehensive error handling:

- **Document not found**: Logs warning and returns early
- **OCR not completed**: Logs warning if `body` is empty or `status != "ready"`
- **LLM service failure**: Catches exception, logs with full context, but **does not** change document status (keeps it as "ready" since OCR succeeded)
- **Database errors**: Handled in finally block to ensure session cleanup

### Logging

Structured logging is used throughout the LLM pipeline:

**In `process_document_llm` Celery task:**
- "Starting LLM analysis" with `document_id`, `domain`, `doc_type`, `text_length`
- "LLM analysis completed successfully" with `document_id`, `summary_length`, `entities_count`
- Error logs include full exception context

**Note**: Full document text and summary are **not** logged to avoid leaking sensitive content. Only metadata (lengths, counts) are logged.

### Key Changes

1. **`app/infrastructure/ai/base.py`**:
   - Added `LlmResult` Pydantic model
   - Extended `LLMService` Protocol with `analyze_document()` method
   - Updated `FakeLLMService` to implement `analyze_document()`

2. **`app/infrastructure/queue/celery_queue.py`**:
   - Added `process_document_llm(document_id)` Celery task
   - Updated `process_document_ocr()` to enqueue LLM task after OCR completes
   - LLM task updates `extracted` field with `summary` and `entities`

3. **`app/api/v1/docs.py`**:
   - Refactored `/analyze` and `/analyze/batch` to use `LlmService` abstraction
   - Maintained same response shapes and field names

4. **`tests/test_llm_service.py`** (new):
   - Unit tests for `FakeLLMService.analyze_document()`
   - Tests for `get_llm_service()` factory

5. **`tests/test_celery_llm.py`** (new):
   - Integration tests for `process_document_llm` Celery task
   - Tests for error cases (document not found, no body, LLM service errors)

### Backward Compatibility

- **API contracts unchanged**: `/analyze` endpoints return the same response shapes
- **Field names unchanged**: `extracted.summary` and `extracted.entities` remain the same
- **Behavior unchanged**: Documents still get analyzed, just using the abstraction layer
- **Status handling**: Document status remains "ready" even if LLM analysis fails (since OCR succeeded)

### Testing

The pipeline can be tested end-to-end:

1. Start services: `docker compose up`
2. Upload a document via Flutter app or PowerShell script
3. Check document status: `GET /api/v1/docs/{doc_id}`
   - Initially shows `status="processing"`
   - After OCR: `status="ready"` with `body` and `excerpt` populated
   - After LLM: `extracted.summary` and `extracted.entities` populated
4. Check worker logs: `docker compose logs worker`
   - Should show "Starting OCR processing"
   - Should show "OCR processing completed successfully"
   - Should show "Starting LLM analysis"
   - Should show "LLM analysis completed successfully"

## CHUNK4: HTTP LLM Service and Configurable Provider Selection

### Goal

Add an `HttpLlmService` implementation behind `LlmService` and a config switch (`LLM_PROVIDER`, `LLM_SERVICE_URL`) so the system can use either `FakeLlmService` (default) or an HTTP-based LLM backend, without changing any API or Celery task signatures.

### LLM Provider Configuration

Two LLM provider modes are now supported:

1. **`fake`** (default): Uses `FakeLLMService` for local development
   - Generates deterministic fake summary and entities
   - No external service calls
   - Fast and suitable for testing

2. **`http`**: Uses `HttpLlmService` to call an external LLM microservice
   - Calls HTTP endpoint at `LLM_SERVICE_URL/analyze`
   - Sends `text`, `mime_type`, and `doc_type` in JSON payload
   - Expects response with `summary` and `entities` fields
   - Maps response to `LlmResult` model

### Configuration

New environment variables:

- **`LLM_PROVIDER`**: Provider selection (`"fake"` or `"http"`, default: `"fake"`)
- **`LLM_SERVICE_URL`**: Base URL for HTTP LLM service (required when `LLM_PROVIDER="http"`)
  - Example: `"http://llm-service:8080"` or `"https://llm.example.com"`

### HttpLlmService Implementation

The `HttpLlmService` class:

- **Initialization**: Takes `base_url`, optional `http_client` (httpx.Client), and optional `timeout` (default: 10.0 seconds)
- **Analyze Method**: 
  - POSTs to `{base_url}/analyze` with JSON payload
  - Handles HTTP errors (status codes, network errors)
  - Validates response format and maps to `LlmResult`
  - Logs metadata only (not full text or summary)
- **Error Handling**:
  - `httpx.HTTPStatusError` for HTTP status errors
  - `httpx.RequestError` for network/timeout errors
  - `ValueError` for invalid response format (missing fields, wrong types)

### Factory Function

The `get_llm_service()` factory function:

- Reads `LLM_PROVIDER` from settings
- Returns `FakeLLMService()` when `LLM_PROVIDER="fake"`
- Returns `HttpLlmService(base_url=settings.LLM_SERVICE_URL)` when `LLM_PROVIDER="http"`
- Raises `RuntimeError` if:
  - `LLM_PROVIDER="http"` but `LLM_SERVICE_URL` is not set
  - `LLM_PROVIDER` has an unsupported value

### HTTP LLM Service Contract

The external LLM microservice should:

- **Endpoint**: `POST /analyze`
- **Request Body**:
  ```json
  {
    "text": "Document text content from OCR...",
    "mime_type": "application/pdf",  // optional
    "doc_type": "PASSPORT"  // optional
  }
  ```
- **Response** (200 OK):
  ```json
  {
    "summary": "Summary of the document content...",
    "entities": [
      {"type": "TOKEN_COUNT", "value": 150},
      {"type": "DOC_TYPE", "value": "PASSPORT"},
      // ... other entities
    ]
  }
  ```

### Running Locally

**With Fake LLM (default):**
```bash
export LLM_PROVIDER=fake
docker compose up
```

**With HTTP LLM Service:**
```bash
export LLM_PROVIDER=http
export LLM_SERVICE_URL=http://llm-service:8080
docker compose up
```

Or in `docker-compose.yml`:
```yaml
environment:
  - LLM_PROVIDER=http
  - LLM_SERVICE_URL=http://llm-service:8080
```

### Testing

Unit tests cover:

- `HttpLlmService`: 
  - Successful analysis with valid response
  - HTTP error handling (non-2xx status codes)
  - Invalid response format handling (missing fields, wrong types)
  - Network/timeout error handling
- `get_llm_service()` factory:
  - Returns correct service based on `LLM_PROVIDER`
  - Error handling for missing/invalid configuration

### Key Changes

1. **`app/core/config.py`**:
   - Added `LLM_PROVIDER: Literal["fake", "http"] = "fake"`
   - Added `LLM_SERVICE_URL: Optional[str] = None`

2. **`app/infrastructure/ai/base.py`**:
   - Added `HttpLlmService` class implementing `LLMService` Protocol
   - Updated `get_llm_service()` to use `LLM_PROVIDER` setting

3. **`docker-compose.yml`**:
   - Added `LLM_PROVIDER=fake` and `LLM_SERVICE_URL=` to api and worker services

4. **`tests/test_llm_service.py`**:
   - Extended with comprehensive tests for `HttpLlmService`
   - Extended tests for `get_llm_service()` with different provider configurations

### Backward Compatibility

- Default behavior unchanged: `LLM_PROVIDER` defaults to `"fake"`
- No changes to API contracts or Celery task signatures
- Existing code using `get_llm_service()` continues to work without modification
- All abstractions preserved (`LlmService` Protocol, `LlmResult` model)

### Design for Future Providers

The factory function design is provider-agnostic, allowing future providers (e.g., `"gemini"`, `"openai"`, `"claude"`) to be added as new branches in `get_llm_service()` without changing existing call sites:

```python
if settings.LLM_PROVIDER == "fake":
    return FakeLLMService()
elif settings.LLM_PROVIDER == "http":
    return HttpLlmService(...)
elif settings.LLM_PROVIDER == "gemini":
    return GeminiLlmService(...)  # Future implementation
# ... etc
```

## CHUNK5: Explicit OCR/LLM Lifecycle Statuses and Reprocessing Endpoints

### Goal

Introduce clear per-step lifecycle fields (`ocr_status`, `llm_status`) on the Document model, wire them into the existing Celery tasks, and add safe reprocessing endpoints to trigger OCR and LLM again when needed. Keep the existing `status` field and response shapes intact for backward compatibility.

### New Status Fields

Two new lifecycle status fields were added to the Document model:

- **`ocr_status`**: Tracks OCR processing lifecycle
  - Values: `"pending"`, `"processing"`, `"ready"`, `"error"`
  - Default: `"pending"` for new documents

- **`llm_status`**: Tracks LLM analysis lifecycle
  - Values: `"pending"`, `"processing"`, `"ready"`, `"error"`
  - Default: `"pending"` for new documents

### Status Field Relationship

The existing `status` field remains unchanged and continues to behave as before:
- Primarily reflects OCR status for backward compatibility
- Set to `"processing"` when OCR starts
- Set to `"ready"` when OCR completes successfully
- Set to `"error"` when OCR fails

The new `ocr_status` and `llm_status` fields provide granular visibility into each processing step independently.

### Lifecycle Flow

**OCR Lifecycle:**
1. **`pending`** → Document created via `/notify`, OCR task enqueued
2. **`processing`** → OCR task starts processing
3. **`ready`** → OCR completes successfully, text extracted
4. **`error`** → OCR fails (storage error, service error, etc.)

**LLM Lifecycle:**
1. **`pending`** → Document created, or OCR completed, LLM task enqueued
2. **`processing`** → LLM task starts analyzing document text
3. **`ready`** → LLM analysis completes successfully, summary and entities extracted
4. **`error`** → LLM analysis fails (service error, invalid response, etc.)

**Combined States:**
- `ocr_status="ready"`, `llm_status="pending"` → OCR done, LLM not started
- `ocr_status="ready"`, `llm_status="processing"` → OCR done, LLM in progress
- `ocr_status="ready"`, `llm_status="ready"` → Both complete
- `ocr_status="error"`, `llm_status="pending"` → OCR failed, LLM never started
- `ocr_status="ready"`, `llm_status="error"` → OCR succeeded, LLM failed (main `status` remains "ready")

### Initialization

When a document is created via `POST /api/v1/docs/notify`:
- `status = "processing"` (existing behavior)
- `ocr_status = "pending"` (new)
- `llm_status = "pending"` (new)

### Celery Task Integration

**`process_document_ocr`:**
- Sets `ocr_status = "processing"` when task starts
- Sets `ocr_status = "ready"` and `status = "ready"` on success
- Sets `ocr_status = "error"` and `status = "error"` on failure
- Enqueues LLM task after successful OCR

**`process_document_llm`:**
- Verifies document has `body` and `status = "ready"` before proceeding
- Sets `llm_status = "processing"` when task starts
- Sets `llm_status = "ready"` on success (does not change `status`)
- Sets `llm_status = "error"` on failure (does not change `status`, since OCR succeeded)
- Sets `llm_status = "error"` if preconditions not met (no body, OCR not ready)

### Reprocessing Endpoints

Two new endpoints were added for manual reprocessing:

**`POST /api/v1/docs/{doc_id}/reprocess/ocr`:**
- Resets `status = "processing"`, `ocr_status = "pending"`, `llm_status = "pending"`
- Enqueues OCR task (which will trigger LLM after completion)
- Returns: `{"message": "OCR reprocessing scheduled", "document_id": <id>}`
- Use case: Re-run OCR if extraction quality is poor or file was updated

**`POST /api/v1/docs/{doc_id}/reprocess/llm`:**
- Requires document to have `body` (OCR must have completed)
- Resets `llm_status = "pending"`
- Enqueues LLM task
- Returns: `{"message": "LLM reprocessing scheduled", "document_id": <id>}`
- Returns 400 if document has no body
- Use case: Re-run LLM analysis with updated prompts or models

Both endpoints are idempotent: calling them multiple times enqueues multiple jobs.

### API Response Changes

The new status fields are exposed in all document responses:

**`GET /api/v1/docs`** (list):
- Each document includes `ocr_status` and `llm_status` fields

**`GET /api/v1/docs/{doc_id}`** (detail):
- Document includes `ocr_status` and `llm_status` fields

**Schemas Updated:**
- `DocOut` and `DocDetailOut` now include `ocr_status: str` and `llm_status: str`
- Existing `status` field remains unchanged

### Key Changes

1. **`app/infrastructure/db/models.py`**:
   - Added `ocr_status: Mapped[str] = mapped_column(String(32), default="pending")`
   - Added `llm_status: Mapped[str] = mapped_column(String(32), default="pending")`

2. **`app/api/v1/docs.py`**:
   - Updated `/notify` to initialize `ocr_status="pending"` and `llm_status="pending"`
   - Added `POST /api/v1/docs/{doc_id}/reprocess/ocr` endpoint
   - Added `POST /api/v1/docs/{doc_id}/reprocess/llm` endpoint

3. **`app/infrastructure/queue/celery_queue.py`**:
   - Updated `process_document_ocr` to manage `ocr_status` lifecycle
   - Updated `process_document_llm` to manage `llm_status` lifecycle
   - Enhanced logging to include new status fields

4. **`app/schemas.py`**:
   - Added `ocr_status: str` and `llm_status: str` to `DocOut` schema

5. **`tests/test_reprocessing.py`** (new):
   - Tests for reprocessing endpoints (success, not found, validation errors)

6. **`tests/test_status_fields.py`** (new):
   - Tests for status field initialization
   - Tests for OCR status lifecycle
   - Tests for LLM status lifecycle
   - Tests that API responses include new fields

### Backward Compatibility

- **Existing `status` field**: Unchanged behavior and semantics
- **API response shapes**: Only additive fields (`ocr_status`, `llm_status`), no removals
- **Celery task signatures**: Unchanged
- **Existing clients**: Continue to work, can optionally use new status fields for better visibility

### Database Migration

The new fields are added to the Document model with defaults:
- New documents: `ocr_status="pending"`, `llm_status="pending"`
- Existing documents: Will have default values when accessed (SQLAlchemy handles this)

For production deployments, a migration script should be run to set appropriate defaults for existing rows:
- Documents with `status="ready"`: `ocr_status="ready"`, `llm_status="ready"` (if `extracted` has summary)
- Documents with `status="error"`: `ocr_status="error"`, `llm_status="pending"` or `"error"` based on context

### Testing

The implementation includes comprehensive tests:
- Status field initialization in `/notify`
- OCR status transitions (pending → processing → ready/error)
- LLM status transitions (pending → processing → ready/error)
- Reprocessing endpoint behavior
- API response field inclusion

### Usage Examples

**Check document processing status:**
```bash
GET /api/v1/docs/123
# Response includes:
# {
#   "status": "ready",
#   "ocr_status": "ready",
#   "llm_status": "ready",
#   ...
# }
```

**Reprocess OCR (e.g., after updating file):**
```bash
POST /api/v1/docs/123/reprocess/ocr
# Resets all statuses and enqueues fresh OCR + LLM
```

**Reprocess LLM only (e.g., with updated model):**
```bash
POST /api/v1/docs/123/reprocess/llm
# Only re-runs LLM analysis, OCR results unchanged
```

## CHUNK6: Observability, Retries, Enums, and Provider Metadata Hardening

### Goal

Make the pipeline production-ready by introducing centralized status enums, structured lifecycle event logs with timing, basic retry policy for OCR/LLM Celery tasks, provider metadata tracking, and improved traceability via IDs.

### Centralized Status Constants

A `PipelineStepStatus` enum was introduced in `app/core/constants.py`:

```python
class PipelineStepStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"
```

This enum is used throughout the codebase to:
- Define default values in the Document model
- Set status transitions in Celery tasks
- Initialize statuses in `/notify` endpoint
- Reset statuses in reprocessing endpoints

All status values remain as strings in the database and JSON for backward compatibility; the enum prevents typos and drift in the codebase.

### Status Transition Validation

Status transition helpers were added in `app/services/status.py`:

- **`set_ocr_status(doc, new_status, reason=None)`**: Validates and sets OCR status
- **`set_llm_status(doc, new_status, reason=None)`**: Validates and sets LLM status

**Allowed transitions:**
- `pending` → `processing`
- `processing` → `ready` / `error`
- `error` → `pending` (reprocessing)
- `ready` → `pending` (reprocessing)

Unexpected transitions are logged as warnings but still allowed (to avoid breaking edge cases).

### Provider Metadata in Extracted Field

Provider metadata is now stored in the `extracted` JSON field in a nested structure:

**OCR Provider Metadata:**
```json
{
  "ocr": {
    "page_count": 1,
    "language": "en",
    "provider": "fake",
    "provider_name": "FakeOcrService"
  }
}
```

**LLM Provider Metadata:**
```json
{
  "llm": {
    "summary": "...",
    "entities": [...],
    "provider": "fake",
    "provider_name": "FakeLLMService"
  }
}
```

**Backward Compatibility:**
- Top-level fields (`summary`, `entities`, `page_count`, `language`) are preserved for existing clients
- New nested structure provides clear provider attribution
- Existing code continues to work without changes

### Lifecycle Event Logs with Timings

Structured event logs are emitted at key lifecycle points:

**OCR Events:**
- `ocr.started`: When OCR task begins processing
- `ocr.success`: When OCR completes successfully
- `ocr.failure`: When OCR fails

**LLM Events:**
- `llm.started`: When LLM task begins processing
- `llm.success`: When LLM completes successfully
- `llm.failure`: When LLM fails

**Log Fields:**
Each event log includes:
- `event`: Event type (e.g., "ocr.success")
- `document_id`: Document being processed
- `celery_task_id`: Celery task ID for correlation
- `request_id`: API request ID (if available)
- `provider`: Provider type ("fake" or "http")
- `provider_name`: Provider class name
- `duration_ms`: Processing duration in milliseconds
- `ocr_status` / `llm_status`: Current status
- Metadata (domain, doc_type, text_length, page_count, language, etc.)

**Example Log Entry:**
```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "logger": "app.infrastructure.queue.celery_queue",
  "message": "OCR processing completed successfully",
  "event": "ocr.success",
  "document_id": 123,
  "celery_task_id": "abc-123-def",
  "request_id": "req-456",
  "status": "ready",
  "ocr_status": "ready",
  "provider": "fake",
  "provider_name": "FakeOcrService",
  "page_count": 1,
  "language": "en",
  "text_length": 1234,
  "duration_ms": 523.45
}
```

### Retry Policy

Both `process_document_ocr` and `process_document_llm` tasks now have retry policies:

**Configuration:**
- `autoretry_for=(httpx.RequestError, httpx.HTTPStatusError)`: Retries on transient HTTP errors
- `retry_backoff=True`: Exponential backoff between retries
- `max_retries=3`: Maximum 3 retry attempts

**Transient Errors (Retried):**
- `httpx.RequestError`: Network errors, timeouts, connection failures
- `httpx.HTTPStatusError`: HTTP 5xx errors from OCR/LLM services

**Non-Transient Errors (Not Retried):**
- Validation errors (e.g., no body, OCR not ready)
- Invalid response format errors
- Other logical errors

**Behavior:**
- Transient errors are re-raised to trigger Celery retry
- Status is only set to "error" after max retries are exhausted
- Non-transient errors set status to "error" immediately and return error response

### Traceability Improvements

**Request ID Tracking:**
- `request_id` field added to Document model (nullable, indexed)
- Set from `X-Request-ID` header or generated UUID in `/notify` endpoint
- Included in all Celery task logs for correlation

**Celery Task ID:**
- `celery_task_id` included in all task logs
- Available via `self.request.id` in bound tasks

**Document ID:**
- Explicitly included in all logs related to a document

**Correlation:**
- API request → Document creation → OCR task → LLM task can be traced via:
  - `request_id` (API → Document → Tasks)
  - `celery_task_id` (Task execution)
  - `document_id` (All operations)

### Key Changes

1. **`app/core/constants.py`** (new):
   - `PipelineStepStatus` enum

2. **`app/services/status.py`** (new):
   - `set_ocr_status()` and `set_llm_status()` helpers with transition validation

3. **`app/infrastructure/db/models.py`**:
   - `ocr_status` and `llm_status` defaults use `PipelineStepStatus.PENDING.value`
   - `request_id` field added (nullable, indexed)

4. **`app/api/v1/docs.py`**:
   - `/notify` uses status helpers and stores `request_id`
   - Reprocessing endpoints use status helpers

5. **`app/infrastructure/queue/celery_queue.py`**:
   - Tasks use `bind=True` for retry support
   - Tasks decorated with `autoretry_for`, `retry_backoff`, `max_retries`
   - Provider metadata stored in nested `extracted.ocr` and `extracted.llm`
   - Structured event logs with `event`, `duration_ms`, `celery_task_id`, `request_id`
   - Transient error handling (retry vs. immediate error)

6. **`tests/test_chunk6.py`** (new):
   - Tests for `PipelineStepStatus` enum
   - Tests for status transition helpers
   - Tests for provider metadata storage
   - Tests for lifecycle event logs
   - Tests for retry policy behavior

### Backward Compatibility

- **Status values**: Still strings in DB/JSON, enum only in code
- **Extracted field**: Top-level fields preserved, nested structure additive
- **API responses**: No breaking changes, only additive fields
- **Celery task signatures**: Unchanged (only decorators added)
- **Existing clients**: Continue to work without modifications

### Usage Examples

**Check provider metadata:**
```bash
GET /api/v1/docs/123
# Response includes:
# {
#   "extracted": {
#     "ocr": {
#       "provider": "fake",
#       "provider_name": "FakeOcrService",
#       "page_count": 1,
#       "language": "en"
#     },
#     "llm": {
#       "provider": "fake",
#       "provider_name": "FakeLLMService",
#       "summary": "...",
#       "entities": [...]
#     }
#   }
# }
```

**Query logs by request_id:**
```bash
# All logs for a single API request → Document → OCR → LLM
grep "request_id.*req-456" logs.json
```

**Query logs by celery_task_id:**
```bash
# All logs for a specific Celery task execution
grep "celery_task_id.*abc-123-def" logs.json
```

## EPIC2 Integration Note

EPIC2-CHUNK1 introduces HTTP gateway stub services that implement the same contracts used by `HttpOcrService` and `HttpLlmService`. These stubs allow local development with HTTP providers instead of fake providers.

See [EPIC2_CHUNK1_GATEWAY.md](./EPIC2_CHUNK1_GATEWAY.md) for:
- Gateway contract specifications
- How to run with stub services
- Validation steps

The gateway contracts are stable and will be used for future cloud deployments (GCP Cloud Run, AWS Lambda, etc.).

## Next Steps

- **CHUNK7**: Add structured field extraction based on `DOC_TYPE_REGISTRY`
- **CHUNK8**: Implement expiry date detection and reminders
- **CHUNK9**: Add vector embeddings for semantic search

