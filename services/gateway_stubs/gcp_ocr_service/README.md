# GCP Vision OCR Gateway Service

Cloud Run deployable OCR service using Google Cloud Vision API.

## Overview

This service implements the OCR gateway contract (`POST /extract`) using Google Cloud Vision API for actual OCR processing. It supports:

- **PDF/TIFF files**: Uses Vision async batch processing with GCS input/output
- **Image files**: Uses direct Vision API text detection
- **Text files**: Reads directly from GCS

## Local Development

### Prerequisites

1. Google Cloud SDK installed and configured
2. Application Default Credentials set up:
   ```bash
   gcloud auth application-default login
   ```
3. Required APIs enabled:
   - Cloud Vision API
   - Cloud Storage API

### Environment Variables

```bash
# Required (if storage_key is not gs:// URL)
GCS_BUCKET=your-bucket-name

# Optional
GCS_OUTPUT_BUCKET=your-bucket-name  # Defaults to GCS_BUCKET
GCS_OUTPUT_PREFIX=ocr-output/        # Default: "ocr-output/"
OCR_TIMEOUT_SECONDS=120              # Default: 120
MAX_BYTES=10485760                   # Default: 10MB
LOG_LEVEL=INFO                       # Default: INFO
PORT=8081                            # Default: 8080 (Cloud Run uses PORT)
```

### Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run service
python main.py
# Or with uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8081
```

### Testing Locally

```bash
# Health check
curl http://localhost:8081/health

# Extract text (using gs:// URL)
curl -X POST http://localhost:8081/extract \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: test-123" \
  -d '{
    "storage_key": "gs://your-bucket/path/to/document.pdf",
    "mime_type": "application/pdf"
  }'

# Extract text (using object path, requires GCS_BUCKET env)
curl -X POST http://localhost:8081/extract \
  -H "Content-Type: application/json" \
  -d '{
    "storage_key": "path/to/document.pdf",
    "mime_type": "application/pdf"
  }'
```

## Cloud Run Deployment

### Build Container

```bash
# Set your GCP project
export PROJECT_ID=your-project-id
export SERVICE_NAME=gcp-ocr-service
export REGION=us-central1

# Build and push to Artifact Registry or Container Registry
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME
```

### Deploy to Cloud Run

```bash
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

### Required IAM Permissions

The service account needs:

- `roles/vision.user` - Vision API access
- `roles/storage.objectViewer` - Read GCS objects
- `roles/storage.objectCreator` - Write OCR output to GCS

### Set Service Account

```bash
# Create service account (if not exists)
gcloud iam service-accounts create ocr-service \
  --display-name="OCR Gateway Service"

# Grant permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:ocr-service@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/vision.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:ocr-service@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:ocr-service@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.objectCreator"
```

## API Contract

### POST /extract

**Request:**
```json
{
  "storage_key": "gs://bucket/path/to/file.pdf",
  "mime_type": "application/pdf"
}
```

**Response:**
```json
{
  "text": "Extracted text content...",
  "page_count": 3,
  "language": "en"
}
```

**Error Responses:**
- `400`: Invalid request (missing storage_key, invalid format)
- `404`: Object not found in GCS
- `413`: File too large (exceeds MAX_BYTES)
- `502`: GCS or Vision API error
- `504`: OCR operation timeout

## Storage Key Formats

The service supports two formats:

1. **Full GCS URL**: `gs://bucket-name/path/to/object.pdf`
2. **Object path only**: `path/to/object.pdf` (requires `GCS_BUCKET` env var)

## OCR Modes

### PDF/TIFF (Async Batch)
- Uses Vision async batch processing
- Writes output JSON to GCS
- Polls until completion (with timeout)
- Concatenates text from all pages

### Images (Direct)
- Downloads image bytes from GCS (size limit: MAX_BYTES)
- Calls Vision text detection API
- Returns extracted text immediately

### Text Files
- Reads directly from GCS as UTF-8 text
- No OCR processing needed

## Logging

Structured logs include:
- `event`: Event type (gcp_ocr.extract.started|success|failure)
- `storage_key`: Storage key (safe, no sensitive data)
- `text_length`: Length of extracted text (not the text itself)
- `page_count`: Number of pages
- `language`: Detected language
- `duration_ms`: Processing duration
- `request_id`: X-Request-ID header if provided

Full extracted text is never logged.

