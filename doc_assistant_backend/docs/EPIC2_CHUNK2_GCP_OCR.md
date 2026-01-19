# EPIC2-CHUNK2: GCP Vision OCR Gateway Service

## Overview

This document describes the GCP Vision OCR gateway service implementation, which uses Google Cloud Vision API to perform OCR while maintaining the same HTTP contract as the local stub service.

## Service Location

`services/gateway_stubs/gcp_ocr_service/`

## Architecture

The service implements the OCR gateway contract (`POST /extract`) using Google Cloud Vision API:

- **PDF/TIFF files**: Uses Vision async batch processing with GCS input/output
- **Image files**: Uses direct Vision API text detection
- **Text files**: Reads directly from GCS (no OCR needed)

## API Contract

Same as EPIC2-CHUNK1 stub service:

**Endpoint:** `POST /extract`

**Request:**
```json
{
  "storage_key": "gs://bucket/path/to/file.pdf",
  "mime_type": "application/pdf"  // optional
}
```

**Response:**
```json
{
  "text": "Extracted text content...",
  "page_count": 3,  // optional
  "language": "en"  // optional
}
```

## Storage Key Formats

The service supports two storage key formats:

1. **Full GCS URL**: `gs://bucket-name/path/to/object.pdf`
   - Parses bucket and object path automatically

2. **Object path only**: `path/to/object.pdf`
   - Requires `GCS_BUCKET` environment variable
   - Uses the object path as-is

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GCS_BUCKET` | Yes* | - | GCS bucket name (required if storage_key is not gs:// URL) |
| `GCS_OUTPUT_BUCKET` | No | `GCS_BUCKET` | GCS bucket for OCR output files |
| `GCS_OUTPUT_PREFIX` | No | `ocr-output/` | GCS prefix for OCR output files |
| `OCR_TIMEOUT_SECONDS` | No | `120` | Timeout for async OCR operations |
| `MAX_BYTES` | No | `10485760` | Maximum file size for direct image OCR (10MB) |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `PORT` | No | `8080` | Server port (Cloud Run uses PORT env var) |

*Required only when storage_key is not a full gs:// URL

## Authentication

Uses Google Application Default Credentials (ADC):

- **Locally**: Run `gcloud auth application-default login`
- **Cloud Run**: Service account attached to the Cloud Run service

## Cloud Run Deployment

### Prerequisites

1. Enable required APIs:
   ```bash
   gcloud services enable vision.googleapis.com
   gcloud services enable storage.googleapis.com
   ```

2. Create service account:
   ```bash
   gcloud iam service-accounts create ocr-service \
     --display-name="OCR Gateway Service"
   ```

3. Grant IAM permissions:
   ```bash
   # Vision API access
   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member="serviceAccount:ocr-service@$PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/vision.user"
   
   # GCS read access
   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member="serviceAccount:ocr-service@$PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/storage.objectViewer"
   
   # GCS write access (for OCR output)
   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member="serviceAccount:ocr-service@$PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/storage.objectCreator"
   ```

### Build and Deploy

```bash
# Set variables
export PROJECT_ID=your-project-id
export SERVICE_NAME=gcp-ocr-service
export REGION=us-central1

# Build container
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME

# Deploy to Cloud Run
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --service-account=ocr-service@$PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars="GCS_BUCKET=your-bucket,GCS_OUTPUT_PREFIX=ocr-output/,OCR_TIMEOUT_SECONDS=120" \
  --memory=2Gi \
  --timeout=300 \
  --max-instances=10
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
3. Set environment variables:
   ```bash
   export GCS_BUCKET=your-bucket-name
   export GCS_OUTPUT_PREFIX=ocr-output/
   ```

### Run Service

```bash
cd services/gateway_stubs/gcp_ocr_service
pip install -r requirements.txt
python main.py
```

### Test Endpoint

```bash
# Health check
curl http://localhost:8081/health

# Extract from PDF (using gs:// URL)
curl -X POST http://localhost:8081/extract \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: test-123" \
  -d '{
    "storage_key": "gs://your-bucket/path/to/document.pdf",
    "mime_type": "application/pdf"
  }'

# Extract from image
curl -X POST http://localhost:8081/extract \
  -H "Content-Type: application/json" \
  -d '{
    "storage_key": "gs://your-bucket/path/to/image.jpg",
    "mime_type": "image/jpeg"
  }'
```

## OCR Processing Modes

### PDF/TIFF (Async Batch)

1. Starts Vision async batch operation
2. Writes output JSON files to `gs://{GCS_OUTPUT_BUCKET}/{GCS_OUTPUT_PREFIX}{job_id}/`
3. Polls operation until completion (with timeout)
4. Reads all output JSON files from GCS
5. Concatenates text from all pages in order
6. Extracts page count and detected language

**Note**: Async operations can take 30-120 seconds depending on document size.

### Images (Direct)

1. Downloads image bytes from GCS (with size limit check)
2. Calls Vision text detection API directly
3. Returns extracted text immediately

**Supported formats**: JPEG, PNG, GIF, BMP, WEBP

### Text Files

1. Reads file directly from GCS as UTF-8 text
2. Returns text without OCR processing

## Error Handling

| Status Code | Condition |
|-------------|-----------|
| `400` | Invalid request (missing storage_key, invalid format) |
| `404` | Object not found in GCS |
| `413` | File too large (exceeds MAX_BYTES for direct image OCR) |
| `502` | GCS or Vision API error |
| `504` | OCR operation timeout (async batch) |
| `500` | Internal server error |

## Logging

Structured logs include:

- `event`: Event type (`gcp_ocr.extract.started|success|failure|async_started|async_completed`)
- `storage_key`: Storage key (safe, no sensitive data)
- `text_length`: Length of extracted text (not the text itself)
- `page_count`: Number of pages
- `language`: Detected language
- `duration_ms`: Processing duration in milliseconds
- `request_id`: X-Request-ID header if provided

**Important**: Full extracted text is never logged to protect sensitive document content.

## Integration with DocAssis

To use this service with DocAssis:

1. Deploy to Cloud Run (or run locally with GCP credentials)
2. Set DocAssis environment variables:
   ```bash
   OCR_PROVIDER=http
   OCR_SERVICE_URL=https://gcp-ocr-service-xxx.run.app
   ```

The service implements the same contract as the local stub, so no changes to DocAssis are required.

## Cost Considerations

- **Vision API**: Charged per page/image processed
- **GCS Storage**: Charged for OCR output files (can be cleaned up periodically)
- **Cloud Run**: Charged for compute time and requests

For production, consider:
- Setting up lifecycle policies to auto-delete OCR output files after N days
- Using Cloud Scheduler to clean up old output files
- Monitoring Vision API quota and costs

## Troubleshooting

### "Object not found" errors

- Verify object exists in GCS: `gsutil ls gs://bucket/path/to/object`
- Check service account has `storage.objectViewer` permission
- Verify bucket name and object path are correct

### Vision API errors

- Check service account has `vision.user` role
- Verify Vision API is enabled: `gcloud services list --enabled | grep vision`
- Check quota limits in Cloud Console

### Timeout errors

- Increase `OCR_TIMEOUT_SECONDS` for large documents
- Consider increasing Cloud Run timeout: `--timeout=600`
- Check Vision API operation status in Cloud Console

### Output files not found

- Verify service account has `storage.objectCreator` permission
- Check `GCS_OUTPUT_BUCKET` and `GCS_OUTPUT_PREFIX` are correct
- Verify output bucket exists and is accessible

## Next Steps

- **EPIC2-CHUNK3**: GCP LLM gateway service (similar pattern)
- **EPIC2-CHUNK4**: GCS storage backend for DocAssis
- **EPIC2-CHUNK5**: Full GCP deployment (Cloud Run, GCS, Pub/Sub)

