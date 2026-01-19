# EPIC2-CHUNK4: Cloud-Native Backend Mode for DocAssis

## Overview

This document describes the cloud-native backend implementation that enables DocAssis to run on Google Cloud Run without Docker Compose dependencies, while preserving existing API contracts.

## Architecture

The cloud-native mode uses:
- **GCS (Google Cloud Storage)**: For document storage with signed URL uploads
- **Firestore**: Optional NoSQL database alternative to PostgreSQL
- **HTTP Task Queue**: Async processing via HTTP calls to `/process` endpoint (alternative to Celery)
- **Cloud Run**: Single service deployment (API + processing)

## Service Location

All implementations are in `doc_assistant_backend/app/infrastructure/`:
- `storage/gcs_backend.py` - GCS storage backend
- `db/firestore_adapter.py` - Firestore database adapter
- `queue/http_queue.py` - HTTP task queue
- `db/db_factory.py` - Database provider factory

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `STORAGE_PROVIDER` | No | `minio` | Storage provider: `minio`, `gcs` |
| `GCS_BUCKET` | Yes* | - | GCS bucket name (required if `STORAGE_PROVIDER=gcs`) |
| `DB_PROVIDER` | No | `sql` | Database provider: `sql`, `firestore` |
| `GOOGLE_PROJECT_ID` | Yes* | - | GCP project ID (required if `DB_PROVIDER=firestore` or `STORAGE_PROVIDER=gcs`) |
| `TASK_QUEUE_PROVIDER` | No | `celery` | Task queue: `celery`, `http`, `cloud_tasks` |
| `PUBLIC_BASE_URL` | Yes* | - | Base URL for HTTP callbacks (required if `TASK_QUEUE_PROVIDER=http`) |
| `OCR_PROVIDER` | No | `fake` | OCR provider: `fake`, `http` |
| `OCR_SERVICE_URL` | Yes* | - | OCR service URL (required if `OCR_PROVIDER=http`) |
| `LLM_PROVIDER` | No | `fake` | LLM provider: `fake`, `http` |
| `LLM_SERVICE_URL` | Yes* | - | LLM service URL (required if `LLM_PROVIDER=http`) |

*Required based on provider selection

### Example Cloud Run Configuration

```bash
STORAGE_PROVIDER=gcs
GCS_BUCKET=docassis-documents
DB_PROVIDER=firestore
GOOGLE_PROJECT_ID=your-project-id
TASK_QUEUE_PROVIDER=http
PUBLIC_BASE_URL=https://api-xxxxx.run.app
OCR_PROVIDER=http
OCR_SERVICE_URL=https://gcp-ocr-service-xxxxx.run.app
LLM_PROVIDER=http
LLM_SERVICE_URL=https://gcp-llm-service-xxxxx.run.app
```

## GCS Storage Backend

### Implementation

The `GCSStorageBackend` implements the `StorageBackend` protocol:
- **Signed URL (V4)**: Generates V4 signed URLs for browser uploads
- **Storage Key Format**: Supports both `gs://bucket/object` and `object/path` formats
- **Application Default Credentials**: Uses Google ADC for authentication

### Storage Key Handling

- **Input**: Accepts `gs://bucket/object` or `object/path`
- **Output**: Always returns `gs://bucket/object` format for consistency
- **OCR Service**: Can pass `gs://` URLs directly to OCR service

### Upload Flow

1. Client calls `POST /api/v1/docs/upload/presign`
2. Backend generates GCS signed URL (V4) via `GCSStorageBackend.presign_upload()`
3. Client uploads file directly to GCS using signed URL
4. Client calls `POST /api/v1/docs/notify` with `storage_key`

### Example

```python
# Backend generates signed URL
storage = GCSStorageBackend()
result = storage.presign_upload(
    key="user_1/uuid/document.pdf",
    content_type="application/pdf"
)
# Returns: {"url": "https://storage.googleapis.com/...", "fields": {}, "key": "gs://bucket/user_1/uuid/document.pdf"}
```

## Firestore Persistence

### Implementation

The `FirestoreDocumentAdapter` provides SQLAlchemy-like interface:
- **Compatible API**: Mimics `db.get()`, `db.query()`, `db.add()`, `db.commit()`, `db.refresh()`
- **String IDs**: Uses Firestore auto-generated string IDs (converted to int for API compatibility)
- **Server Timestamps**: Uses Firestore server timestamps for `created_at` and `updated_at`

### Document Fields

All fields from SQLAlchemy model are preserved:
- `id`, `owner_id`, `title`, `filename`, `s3_key`, `size`, `mime`
- `status`, `ocr_status`, `llm_status`
- `excerpt`, `body`, `extracted` (JSON)
- `domain`, `doc_type`, `expiry_date`
- `request_id`, `created_at`, `updated_at`

### Query Limitations

The Firestore adapter supports basic queries:
- `db.get(Document, doc_id)` - Get by ID
- `db.query(Document).filter(Document.owner_id == 1).all()` - Filter queries
- `db.query(Document).filter(Document.status == "ready").all()` - Status filters
- `db.query(Document).order_by(Document.id.desc()).all()` - Ordering

Complex SQL queries may need to be adapted for Firestore.

## HTTP Task Queue

### Implementation

The `HttpTaskQueue` calls the backend's `/process` endpoint:
- **Fire-and-Forget**: Makes async HTTP call with short timeout
- **Best-Effort**: Errors are logged but not raised
- **Self-Call**: Calls `{PUBLIC_BASE_URL}/api/v1/docs/{doc_id}/process`

### Processing Endpoint

**Endpoint**: `POST /api/v1/docs/{doc_id}/process`

**Request**:
```json
{
  "step": "ocr" | "llm" | "all"  // Optional, default: "all"
}
```

**Response**:
```json
{
  "success": true,
  "document_id": 123,
  "step": "all",
  "results": {
    "ocr": {"success": true, "page_count": 3, "language": "en"},
    "llm": {"success": true, "summary_length": 120, "entities_count": 5}
  }
}
```

### Processing Flow

1. **Client calls** `POST /api/v1/docs/notify`
2. Backend creates document record
3. Backend calls `HttpTaskQueue.enqueue_ocr(doc_id)`
4. HTTP task queue makes async POST to `/process` endpoint
5. `/process` endpoint runs OCR and LLM synchronously
6. Document status updated in database

## Cloud Run Deployment

### Prerequisites

1. **Enable APIs**:
   ```bash
   gcloud services enable run.googleapis.com
   gcloud services enable storage.googleapis.com
   gcloud services enable firestore.googleapis.com
   ```

2. **Create GCS Bucket**:
   ```bash
   gsutil mb -p $PROJECT_ID -l us-central1 gs://docassis-documents
   ```

3. **Create Firestore Database** (if using Firestore):
   ```bash
   gcloud firestore databases create --region=us-central1
   ```

4. **Set up IAM**:
   ```bash
   # Service account needs:
   # - roles/storage.objectAdmin (for GCS)
   # - roles/datastore.user (for Firestore)
   # - roles/run.invoker (for HTTP task queue self-calls)
   ```

### Build and Deploy

```bash
# Set variables
export PROJECT_ID=your-project-id
export SERVICE_NAME=docassis-api
export REGION=us-central1
export GCS_BUCKET=docassis-documents

# Build container
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME

# Deploy to Cloud Run
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars="STORAGE_PROVIDER=gcs,GCS_BUCKET=$GCS_BUCKET,DB_PROVIDER=firestore,GOOGLE_PROJECT_ID=$PROJECT_ID,TASK_QUEUE_PROVIDER=http,PUBLIC_BASE_URL=https://$SERVICE_NAME-xxxxx.run.app,OCR_PROVIDER=http,OCR_SERVICE_URL=https://gcp-ocr-service-xxxxx.run.app,LLM_PROVIDER=http,LLM_SERVICE_URL=https://gcp-llm-service-xxxxx.run.app" \
  --memory=2Gi \
  --timeout=300 \
  --max-instances=10 \
  --cpu=2
```

### Update Service

```bash
# Rebuild and redeploy
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --region $REGION
```

## Upload Flow (Cloud Mode)

### Step 1: Get Presigned Upload URL

```bash
curl -X POST https://api-xxxxx.run.app/api/v1/docs/upload/presign \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "document.pdf",
    "mime_type": "application/pdf",
    "size_bytes": 1024000,
    "domain": "IDENTITY",
    "doc_type": "PASSPORT"
  }'
```

**Response**:
```json
{
  "storage_key": "gs://docassis-documents/user_1/uuid/document.pdf",
  "upload_url": "https://storage.googleapis.com/...",
  "upload_fields": {},
  "max_size_bytes": 26214400
}
```

### Step 2: Upload File to GCS

```bash
curl -X PUT "<upload_url>" \
  -H "Content-Type: application/pdf" \
  --data-binary @document.pdf
```

### Step 3: Notify Backend

```bash
curl -X POST https://api-xxxxx.run.app/api/v1/docs/notify \
  -H "Content-Type: application/json" \
  -d '{
    "storage_key": "gs://docassis-documents/user_1/uuid/document.pdf",
    "filename": "document.pdf",
    "mime_type": "application/pdf",
    "size_bytes": 1024000,
    "domain": "IDENTITY",
    "doc_type": "PASSPORT"
  }'
```

**Response**: Document record with `id`, `status="processing"`

### Step 4: Processing (Automatic)

1. Backend creates document record
2. Backend calls `HttpTaskQueue.enqueue_ocr(doc_id)`
3. HTTP task queue makes async POST to `/process` endpoint
4. `/process` endpoint runs OCR → LLM
5. Document status updated to `ready`

### Step 5: Poll Document Status

```bash
curl https://api-xxxxx.run.app/api/v1/docs/{doc_id}
```

**Response**:
```json
{
  "id": 123,
  "status": "ready",
  "ocr_status": "ready",
  "llm_status": "ready",
  "body": "Extracted text...",
  "extracted": {
    "ocr": {"page_count": 3, "language": "en"},
    "llm": {"summary": "...", "entities": [...]}
  }
}
```

## Processing Endpoint

### Manual Processing

You can also trigger processing manually:

```bash
# Process OCR only
curl -X POST https://api-xxxxx.run.app/api/v1/docs/{doc_id}/process \
  -H "Content-Type: application/json" \
  -d '{"step": "ocr"}'

# Process LLM only
curl -X POST https://api-xxxxx.run.app/api/v1/docs/{doc_id}/process \
  -H "Content-Type: application/json" \
  -d '{"step": "llm"}'

# Process both (default)
curl -X POST https://api-xxxxx.run.app/api/v1/docs/{doc_id}/process \
  -H "Content-Type: application/json" \
  -d '{"step": "all"}'
```

## Backward Compatibility

### Local Development

The local Docker Compose flow continues to work:
- `STORAGE_PROVIDER=minio` (or `STORAGE_BACKEND=s3_minio`)
- `DB_PROVIDER=sql` (PostgreSQL)
- `TASK_QUEUE_PROVIDER=celery` (Celery + Redis)

### API Contracts

All API endpoints remain unchanged:
- `POST /api/v1/docs/upload/presign` - Same request/response
- `POST /api/v1/docs/notify` - Same request/response
- `GET /api/v1/docs/{doc_id}` - Same response format
- `GET /api/v1/docs` - Same query parameters

### Storage Key Format

- **Local (MinIO)**: `user_1/uuid/document.pdf`
- **Cloud (GCS)**: `gs://bucket/user_1/uuid/document.pdf` or `user_1/uuid/document.pdf`

Both formats are supported in cloud mode.

## Error Handling

### GCS Errors

- **404**: Object not found → `HTTPException(404)`
- **403**: Permission denied → `HTTPException(502)`
- **Storage errors**: Logged and returned as `502 Bad Gateway`

### Firestore Errors

- **Document not found**: Returns `None` (compatible with SQLAlchemy)
- **Permission errors**: Logged and returned as `500 Internal Server Error`

### HTTP Task Queue Errors

- **Timeout**: Expected for fire-and-forget, logged as debug
- **HTTP errors**: Logged as warning, processing may be retried manually
- **Network errors**: Logged as error, processing may be retried manually

## Logging

All operations use structured logging:
- **Metadata only**: No document text or summaries in logs
- **Request ID**: Propagated through all operations
- **Provider info**: Logs include `storage_provider`, `db_provider`, `task_queue_provider`

Example log entry:
```json
{
  "event": "ocr.started",
  "document_id": 123,
  "request_id": "abc-123",
  "storage_provider": "gcs",
  "db_provider": "firestore",
  "task_queue_provider": "http",
  "storage_key": "gs://bucket/path",
  "mime_type": "application/pdf"
}
```

## Testing

### Unit Tests

```bash
# Test GCS storage
pytest tests/test_gcs_storage.py

# Test Firestore adapter
pytest tests/test_firestore_adapter.py

# Test HTTP task queue
pytest tests/test_http_queue.py
```

### Integration Tests

```bash
# Test cloud mode processing
pytest tests/test_cloud_mode.py
```

## Troubleshooting

### "GCS_BUCKET not set" error

- Verify `GCS_BUCKET` environment variable is set
- Check `STORAGE_PROVIDER=gcs` is configured

### "PUBLIC_BASE_URL not set" error

- Set `PUBLIC_BASE_URL` to your Cloud Run service URL
- Format: `https://service-name-xxxxx.run.app` (no trailing slash)

### Firestore "Permission denied" errors

- Verify service account has `roles/datastore.user` role
- Check Firestore database exists in the project

### HTTP task queue not triggering

- Check `PUBLIC_BASE_URL` is correct and accessible
- Verify `/process` endpoint is working: `curl -X POST $PUBLIC_BASE_URL/api/v1/docs/1/process`
- Check Cloud Run logs for HTTP task queue errors

### Processing stuck in "processing" status

- Check `/process` endpoint logs
- Verify OCR/LLM service URLs are correct and accessible
- Check document `ocr_status` and `llm_status` fields for detailed error info

## Next Steps

- **EPIC2-CHUNK5**: Full GCP deployment with Cloud Tasks (replacing HTTP task queue)
- **EPIC3**: Advanced features (multi-region, caching, rate limiting)
