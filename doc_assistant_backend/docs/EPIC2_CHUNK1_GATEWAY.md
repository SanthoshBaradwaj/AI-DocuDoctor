# EPIC2-CHUNK1: Gateway Contracts + Local Stub Services

## Overview

This document describes the HTTP gateway contracts for OCR and LLM services, and how to run the local stub services for development.

**Note**: For production GCP deployment:
- Real Vision API OCR: See [EPIC2_CHUNK2_GCP_OCR.md](./EPIC2_CHUNK2_GCP_OCR.md)
- Real Gemini LLM: See [EPIC2_CHUNK3_GCP_LLM.md](./EPIC2_CHUNK3_GCP_LLM.md)

## Gateway Contracts

### OCR Gateway Service

**Endpoint:** `POST /extract`

**Request:**
```json
{
  "storage_key": "user_1/uuid/filename.pdf",
  "mime_type": "application/pdf"  // optional
}
```

**Response (200 OK):**
```json
{
  "text": "Extracted text content...",
  "page_count": 1,  // optional
  "language": "en"  // optional
}
```

**Error Responses:**
- `404 Not Found`: Object not found in storage
  ```json
  {"detail": "Object not found: <storage_key>"}
  ```
- `502 Bad Gateway`: Storage/MinIO error
  ```json
  {"detail": "Storage error: <error_message>"}
  ```

**Contract Notes:**
- `storage_key` is required and must reference an object in MinIO/S3
- `mime_type` is optional
- Response must include `text` field (required)
- `page_count` and `language` are optional but recommended

### LLM Gateway Service

**Endpoint:** `POST /analyze`

**Request:**
```json
{
  "text": "Document text content to analyze...",
  "mime_type": "text/plain",  // optional
  "doc_type": "PASSPORT"      // optional
}
```

**Response (200 OK):**
```json
{
  "summary": "Summary of the document...",
  "entities": [
    {"type": "TOKEN_COUNT", "value": 123},
    {"type": "DOC_TYPE", "value": "PASSPORT"},
    {"type": "FAKE_TAG", "value": "stub_llm_service"}
  ]
}
```

**Error Responses:**
- `400 Bad Request`: Missing or empty text
  ```json
  {"detail": "Text is required and cannot be empty"}
  ```

**Contract Notes:**
- `text` is required and cannot be empty
- `mime_type` and `doc_type` are optional
- Response must include `summary` field (required, string)
- Response must include `entities` field (required, array of objects)
- Each entity object should have `type` and `value` fields

## Local Stub Services

### Architecture

The stub services are lightweight FastAPI applications that:
- Implement the gateway contracts exactly
- Provide deterministic behavior for local development
- Can read from MinIO (OCR service) or generate fake results (both)

### OCR Service Stub

**Location:** `services/gateway_stubs/ocr_service/`

**Behavior:**
- For `.txt` files or `text/*` MIME types: Reads actual content from MinIO
- For other file types: Returns deterministic fake text based on `storage_key` and `mime_type`
- Always returns `page_count=1` and `language="en"`

**Environment Variables:**
- `MINIO_ENDPOINT`: MinIO endpoint URL (default: `http://minio:9000`)
- `MINIO_ACCESS_KEY`: MinIO access key (default: `minioadmin`)
- `MINIO_SECRET_KEY`: MinIO secret key (default: `minioadmin`)
- `MINIO_BUCKET`: MinIO bucket name (default: `docs`)
- `MINIO_USE_SSL`: Whether to use SSL (default: `false`)

**Port:** 8081

### LLM Service Stub

**Location:** `services/gateway_stubs/llm_service/`

**Behavior:**
- Generates deterministic summary: First 240 characters of text + " [stub summary]"
- Generates deterministic entities:
  - `TOKEN_COUNT`: Approximate token count (word count)
  - `DOC_TYPE`: Included if `doc_type` is provided in request
  - `FAKE_TAG`: Always included with value "stub_llm_service"

**Port:** 8082

## Running with Stub Services

### Prerequisites

- Docker and Docker Compose installed
- Access to the repository root

### Option 1: Using Compose Override (Recommended)

The default `docker-compose.yml` uses fake providers. To use HTTP stub services:

```bash
cd doc_assistant_backend
docker compose -f docker-compose.yml -f docker-compose.http-stubs.yml up --build
```

This will:
1. Start all base services (db, redis, minio, api, worker)
2. Start OCR and LLM stub services
3. Configure API and worker to use HTTP providers

### Option 2: Manual Environment Override

You can also manually set environment variables:

```bash
cd doc_assistant_backend
docker compose up --build \
  -e OCR_PROVIDER=http \
  -e OCR_SERVICE_URL=http://ocr-service:8081 \
  -e LLM_PROVIDER=http \
  -e LLM_SERVICE_URL=http://llm-service:8082
```

### Verify Services Are Running

Check that all services are healthy:

```bash
# Check OCR service
curl http://localhost:8081/health

# Check LLM service
curl http://localhost:8082/health

# Check API
curl http://localhost:8000/api/v1/health
```

## Validation Steps

### 1. Start the Stack

```bash
cd doc_assistant_backend
docker compose -f docker-compose.yml -f docker-compose.http-stubs.yml up --build
```

Wait for all services to be healthy (check logs or use `docker compose ps`).

### 2. Upload a Test File

**Step 2a: Get presigned upload URL**

```bash
curl -X POST http://localhost:8000/api/v1/docs/upload/presign \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: test-request-123" \
  -d '{
    "filename": "test.txt",
    "mime_type": "text/plain",
    "size_bytes": 100,
    "domain": "IDENTITY",
    "doc_type": "PASSPORT"
  }'
```

Save the `storage_key` and `upload_url` from the response.

**Step 2b: Upload file to MinIO**

```bash
# Create a test file
echo "This is a test document for OCR and LLM processing." > test.txt

# Upload using the presigned URL (adjust fields based on response)
curl -X POST <upload_url> \
  -F "file=@test.txt"
```

**Step 2c: Notify backend**

```bash
curl -X POST http://localhost:8000/api/v1/docs/notify \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: test-request-123" \
  -d '{
    "storage_key": "<storage_key_from_presign>",
    "filename": "test.txt",
    "mime_type": "text/plain",
    "size_bytes": 100,
    "domain": "IDENTITY",
    "doc_type": "PASSPORT"
  }'
```

Save the `id` from the response.

### 3. Poll Document Status

```bash
# Poll until status is "ready" (adjust document_id)
DOC_ID=<id_from_notify>
while true; do
  STATUS=$(curl -s http://localhost:8000/api/v1/docs/$DOC_ID | jq -r '.status')
  echo "Status: $STATUS"
  if [ "$STATUS" = "ready" ]; then
    break
  fi
  sleep 2
done
```

### 4. Verify Provider Metadata

```bash
# Get document details
curl -s http://localhost:8000/api/v1/docs/$DOC_ID | jq '.extracted'
```

Expected output should include:
```json
{
  "ocr": {
    "provider": "http",
    "provider_name": "HttpOcrService",
    "page_count": 1,
    "language": "en"
  },
  "llm": {
    "provider": "http",
    "provider_name": "HttpLlmService",
    "summary": "...",
    "entities": [...]
  }
}
```

### 5. Verify Text Content

For text files, verify that the OCR service read actual content:

```bash
curl -s http://localhost:8000/api/v1/docs/$DOC_ID | jq -r '.body'
```

Should contain the actual text from `test.txt`, not fake text.

## Validation Script

A simple validation script is provided at `doc_assistant_backend/scripts/validate_http_stubs.sh`.

**Usage:**
```bash
cd doc_assistant_backend
chmod +x scripts/validate_http_stubs.sh
./scripts/validate_http_stubs.sh
```

The script will:
1. Check service health
2. Create a test file
3. Upload via presign → notify
4. Poll until ready
5. Print key fields (status, ocr_status, llm_status, providers)

## Troubleshooting

### OCR Service Cannot Connect to MinIO

- Verify MinIO is running: `docker compose ps minio`
- Check MinIO endpoint: `curl http://localhost:9000/minio/health/live`
- Verify environment variables in `docker-compose.http-stubs.yml`

### LLM Service Returns Empty Summary

- Check that text is being passed correctly
- Verify request format matches contract
- Check service logs: `docker compose logs llm-service`

### Document Stuck in "processing" Status

- Check worker logs: `docker compose logs worker`
- Check OCR/LLM service logs: `docker compose logs ocr-service llm-service`
- Verify services are healthy: `docker compose ps`

## Integration with EPIC1

The gateway stub services integrate seamlessly with EPIC1:

- **Provider Selection**: Set `OCR_PROVIDER=http` and `LLM_PROVIDER=http` to use stubs
- **Provider Metadata**: Stubs are identified as `HttpOcrService` and `HttpLlmService` in `extracted` field
- **Retry Policy**: Transient errors from stubs trigger Celery retries (as configured in EPIC1-CHUNK6)
- **Logging**: All lifecycle events are logged with provider information

## Future Cloud Deployment

These stub services represent the gateway interface that will be deployed on:

- **GCP**: Cloud Run or Cloud Functions
- **AWS**: Lambda functions
- **Azure**: Azure Functions

The contracts remain stable; only the implementation changes (e.g., calling Google Vision API instead of reading from MinIO).

