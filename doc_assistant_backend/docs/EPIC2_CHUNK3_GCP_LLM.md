# EPIC2-CHUNK3: GCP Gemini LLM Gateway Service

## Overview

This document describes the GCP Gemini LLM gateway service implementation, which uses Google Cloud Vertex AI with Gemini models to analyze documents while maintaining the same HTTP contract as the local stub service.

## Service Location

`services/gateway_stubs/gcp_llm_service/`

## Architecture

The service implements the LLM gateway contract (`POST /analyze`) using Google Cloud Vertex AI Gemini:

- **Document Analysis**: Uses Gemini models to extract summaries and entities from document text
- **JSON Parsing**: Robustly parses JSON responses from Gemini with fallback to plain text
- **Entity Extraction**: Automatically includes `TOKEN_COUNT` and `DOC_TYPE` entities
- **Application Default Credentials**: Uses Google ADC for authentication (works locally and on Cloud Run)

## API Contract

Same as EPIC2-CHUNK1 stub service:

**Endpoint:** `POST /analyze`

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
- `TOKEN_COUNT`: Approximate token count (always included, calculated by whitespace split)
- `DOC_TYPE`: Document type (included if `doc_type` provided in request)

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GCP_REGION` | No | `us-central1` | GCP region for Vertex AI |
| `MODEL_NAME` | No | `gemini-1.5-flash` | Gemini model to use |
| `MAX_CHARS` | No | `50000` | Maximum text length in characters |
| `REQUEST_TIMEOUT_SECONDS` | No | `15` | Request timeout in seconds |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `PORT` | No | `8080` | Server port (Cloud Run uses PORT env var) |

## Authentication

Uses Google Application Default Credentials (ADC):

- **Locally**: Run `gcloud auth application-default login`
- **Cloud Run**: Service account attached to the Cloud Run service

## Cloud Run Deployment

### Prerequisites

1. Enable required APIs:
   ```bash
   gcloud services enable aiplatform.googleapis.com
   ```

2. Create service account:
   ```bash
   gcloud iam service-accounts create llm-service \
     --display-name="LLM Gateway Service"
   ```

3. Grant IAM permissions:
   ```bash
   # Vertex AI access
   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member="serviceAccount:llm-service@$PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/aiplatform.user"
   ```

### Build and Deploy

```bash
# Set variables
export PROJECT_ID=your-project-id
export SERVICE_NAME=gcp-llm-service
export REGION=us-central1

# Build container
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME

# Deploy to Cloud Run
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --service-account=llm-service@$PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars="GCP_REGION=$REGION,MODEL_NAME=gemini-1.5-flash,MAX_CHARS=50000,REQUEST_TIMEOUT_SECONDS=15" \
  --memory=1Gi \
  --timeout=60 \
  --max-instances=10 \
  --cpu=1
```

### Update Service

```bash
# Rebuild and redeploy
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --region $REGION
```

## Local Testing

### Setup

1. Install Google Cloud SDK
2. Authenticate:
   ```bash
   gcloud auth application-default login
   ```
3. Set environment variables (optional):
   ```bash
   export GCP_REGION=us-central1
   export MODEL_NAME=gemini-1.5-flash
   export MAX_CHARS=50000
   ```

### Run Service

```bash
cd services/gateway_stubs/gcp_llm_service
pip install -r requirements.txt
python main.py
```

### Test Endpoint

```bash
# Health check
curl http://localhost:8080/health

# Analyze document
curl -X POST http://localhost:8080/analyze \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: test-123" \
  -d '{
    "text": "This is a sample document about a passport. The passport number is AB123456. It was issued on 2024-01-15.",
    "doc_type": "PASSPORT",
    "mime_type": "text/plain"
  }'
```

## LLM Processing

### Request Flow

1. **Validation**: Checks text is non-empty and within `MAX_CHARS` limit
2. **Token Counting**: Calculates approximate token count (whitespace split)
3. **Prompt Building**: Constructs prompt asking Gemini for JSON response with summary and entities
4. **Gemini Call**: Calls Vertex AI Gemini with timeout handling
5. **JSON Parsing**: Attempts to parse JSON from response (handles markdown code blocks)
6. **Fallback**: If JSON parsing fails, uses response text as summary with minimal entities
7. **Entity Normalization**: Ensures all entities have `type` and `value` fields
8. **Required Entities**: Adds `TOKEN_COUNT` and `DOC_TYPE` (if provided) to entities list

### JSON Parsing Strategy

The service uses a robust multi-step JSON extraction:

1. **Markdown Code Blocks**: Looks for JSON in ````json ... ``` blocks
2. **Direct JSON**: Searches for JSON object pattern `{...}`
3. **Full Text Parse**: Attempts to parse entire response as JSON
4. **Fallback**: If all parsing fails, uses response text as summary

This ensures the service works even if Gemini returns slightly malformed JSON or includes extra text.

## Error Handling

| Status Code | Condition |
|-------------|-----------|
| `400` | Missing or empty `text` field |
| `413` | Text length exceeds `MAX_CHARS` |
| `502` | Vertex AI API error (permission, quota, etc.) |
| `504` | Request timeout exceeded |
| `500` | Internal server error |

## Logging

Structured logs include:

- `event`: Event type (`gcp_llm.analyze.started|success|failure|timeout|vertex_error`)
- `request_id`: X-Request-ID header if provided
- `text_length`: Length of input text (not the text itself)
- `token_count`: Approximate token count
- `doc_type`: Document type if provided
- `mime_type`: MIME type if provided
- `model_name`: Gemini model used
- `summary_length`: Length of generated summary (not the summary itself)
- `entities_count`: Number of entities extracted
- `duration_ms`: Processing duration in milliseconds

**Important**: Full text and summaries are never logged to protect sensitive document content.

## Integration with DocAssis

To use this service with DocAssis:

1. Deploy to Cloud Run (or run locally with GCP credentials)
2. Set DocAssis environment variables:
   ```bash
   LLM_PROVIDER=http
   LLM_SERVICE_URL=https://gcp-llm-service-xxx.run.app
   ```

The service implements the same contract as the local stub, so no changes to DocAssis are required.

## Model Selection

### Available Models

- `gemini-1.5-flash` (default): Fast, cost-effective, good for most use cases
- `gemini-1.5-pro`: More capable, better for complex documents
- `gemini-pro`: Legacy model (use 1.5 versions if available)

### Model Configuration

The service uses these generation parameters:

- `temperature`: 0.1 (low for consistent, factual output)
- `max_output_tokens`: 2048 (sufficient for summaries and entities)

To customize, modify the `generation_config` in `call_gemini_async()`.

## Cost Considerations

- **Vertex AI**: Charged per token (input + output)
- **Cloud Run**: Charged for compute time and requests
- **Network**: Minimal (text-only requests)

For production, consider:

- Using `gemini-1.5-flash` for cost efficiency (default)
- Setting appropriate `MAX_CHARS` to limit input size
- Monitoring Vertex AI quota and costs in Cloud Console
- Implementing request rate limiting if needed

## Troubleshooting

### "Permission denied" errors

- Check service account has `roles/aiplatform.user` role
- Verify Vertex AI API is enabled: `gcloud services list --enabled | grep aiplatform`
- Ensure service account is attached to Cloud Run service

### Timeout errors

- Increase `REQUEST_TIMEOUT_SECONDS` for longer documents
- Consider increasing Cloud Run timeout: `--timeout=120`
- Check Vertex AI API status in Cloud Console

### JSON parsing failures

- Check logs for `gcp_llm.gemini.json_parse_failed` events
- Service will fallback to using response text as summary
- Consider adjusting prompt in `build_prompt()` to be more explicit about JSON format

### Empty or invalid responses

- Verify model name is correct (e.g., `gemini-1.5-flash`)
- Check Vertex AI quota limits in Cloud Console
- Review logs for specific error messages

### High costs

- Switch to `gemini-1.5-flash` (cheaper than `gemini-1.5-pro`)
- Reduce `MAX_CHARS` to limit input size
- Monitor usage in Cloud Console billing

## Testing

### Unit Tests

```bash
cd services/gateway_stubs/gcp_llm_service
pytest test_main.py -v
```

Tests cover:
- Token counting
- JSON extraction
- Prompt building
- Request validation
- Error handling
- Entity normalization

### Integration Testing

For integration tests with real Gemini API:

1. Set up ADC: `gcloud auth application-default login`
2. Run service: `python main.py`
3. Test with real documents using curl or Postman

## Next Steps

- **EPIC2-CHUNK4**: GCS storage backend for DocAssis
- **EPIC2-CHUNK5**: Full GCP deployment (Cloud Run, GCS, Pub/Sub)
- **EPIC3**: Advanced features (multi-language support, custom entity extraction)
