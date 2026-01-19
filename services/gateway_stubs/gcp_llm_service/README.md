# GCP Gemini LLM Gateway Service

A production-ready FastAPI service that provides document analysis using Google Cloud Vertex AI Gemini models. This service implements the `/analyze` endpoint contract expected by DocAssis backend.

## Features

- **Vertex AI Gemini Integration**: Uses Google Cloud Vertex AI with Gemini models for document analysis
- **Application Default Credentials (ADC)**: Authenticates using Google ADC (works locally and on Cloud Run)
- **Robust JSON Parsing**: Handles JSON responses from Gemini with fallback to plain text
- **Metadata-Only Logging**: Logs only metadata, never full text or summaries
- **Cloud Run Ready**: Containerized and optimized for Google Cloud Run deployment
- **Comprehensive Error Handling**: Proper HTTP status codes (400, 413, 502, 504, 500)

## API Contract

### POST /analyze

Analyzes a document and extracts summary and entities.

**Request:**
```json
{
  "text": "Document text content...",
  "mime_type": "text/plain",  // optional
  "doc_type": "PASSPORT"       // optional
}
```

**Response:**
```json
{
  "summary": "Brief summary of the document",
  "entities": [
    {"type": "TOKEN_COUNT", "value": 150},
    {"type": "DOC_TYPE", "value": "PASSPORT"},
    {"type": "DATE", "value": "2024-01-15"},
    ...
  ]
}
```

**Required Entities:**
- `TOKEN_COUNT`: Approximate token count (always included)
- `DOC_TYPE`: Document type (included if `doc_type` provided in request)

## Configuration

Environment variables:

- `GCP_REGION` (default: `us-central1`): GCP region for Vertex AI
- `MODEL_NAME` (default: `gemini-1.5-flash`): Gemini model to use
- `MAX_CHARS` (default: `50000`): Maximum text length in characters
- `REQUEST_TIMEOUT_SECONDS` (default: `15`): Request timeout in seconds
- `LOG_LEVEL` (default: `INFO`): Logging level
- `PORT` (default: `8080`): Server port (Cloud Run sets this automatically)

## Local Development

### Prerequisites

1. Google Cloud SDK installed and configured
2. Application Default Credentials set up:
   ```bash
   gcloud auth application-default login
   ```
3. Vertex AI API enabled in your GCP project
4. Required IAM role: `roles/aiplatform.user`

### Run Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run service
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8080
```

### Test

```bash
# Run unit tests
pytest test_main.py -v

# Test endpoint manually
curl -X POST http://localhost:8080/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "text": "This is a test document with some content.",
    "doc_type": "TEST"
  }'
```

## Docker

### Build

```bash
docker build -t gcp-llm-service .
```

### Run

```bash
docker run -p 8080:8080 \
  -e GCP_REGION=us-central1 \
  -e MODEL_NAME=gemini-1.5-flash \
  gcp-llm-service
```

## Cloud Run Deployment

See `doc_assistant_backend/docs/EPIC2_CHUNK3_GCP_LLM.md` for detailed deployment instructions.

Quick deploy:

```bash
gcloud run deploy gcp-llm-service \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GCP_REGION=us-central1,MODEL_NAME=gemini-1.5-flash
```

## Integration with DocAssis

Set these environment variables in your DocAssis backend:

```bash
LLM_PROVIDER=http
LLM_SERVICE_URL=https://gcp-llm-service-xxxxx.run.app
```

The DocAssis backend will automatically use this service for LLM analysis.

## Error Handling

- **400 Bad Request**: Missing or empty `text` field
- **413 Payload Too Large**: Text exceeds `MAX_CHARS`
- **502 Bad Gateway**: Vertex AI API errors
- **504 Gateway Timeout**: Request timeout exceeded
- **500 Internal Server Error**: Unexpected errors

## Logging

All logs are structured and metadata-only. Example log entry:

```json
{
  "event": "gcp_llm.analyze.success",
  "request_id": "abc-123",
  "text_length": 1500,
  "token_count": 250,
  "doc_type": "PASSPORT",
  "mime_type": "text/plain",
  "model_name": "gemini-1.5-flash",
  "summary_length": 120,
  "entities_count": 5,
  "duration_ms": 1234.56
}
```

## License

Part of the DocAssis project.
