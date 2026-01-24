# Flutter App - Cloud Run Integration Guide

This guide explains how to run the Flutter app against Cloud Run backend services.

## Prerequisites

- Flutter SDK installed
- Backend services deployed to Cloud Run:
  - `docassis-api` (main API)
  - `gcp-llm-service` (LLM gateway)
- Cloud Run URLs for your services

## Configuration

### Option 1: Environment Variables (Recommended)

Set the Cloud Run API base URL when running the app:

```bash
# Web
flutter run -d chrome --dart-define=CLOUD_RUN_API_BASE=https://docassis-api-xxxxx.run.app/api/v1

# Android
flutter run --dart-define=CLOUD_RUN_API_BASE=https://docassis-api-xxxxx.run.app/api/v1
```

### Option 2: Update config.dart

Edit `lib/config.dart` and set `kCloudRunApiBase`:

```dart
const String kCloudRunApiBase = 'https://docassis-api-xxxxx.run.app/api/v1';
```

Then rebuild the app.

## Running the App

### Web (Chrome)

```bash
flutter run -d chrome --dart-define=CLOUD_RUN_API_BASE=https://docassis-api-xxxxx.run.app/api/v1
```

### Android

```bash
flutter run --dart-define=CLOUD_RUN_API_BASE=https://docassis-api-xxxxx.run.app/api/v1
```

## Test Mode

Test mode allows you to open chat directly with a hardcoded document ID (useful for debugging).

Enable test mode:

```bash
flutter run -d chrome --dart-define=TEST_MODE=true --dart-define=CLOUD_RUN_API_BASE=https://docassis-api-xxxxx.run.app/api/v1
```

In test mode, navigating to `/chat` will automatically open chat for document ID 1.

## Features

### Upload Flow

1. **Pick File**: Select a PDF from device
2. **Presign**: Get presigned upload URL from backend
3. **Upload**: Upload file to storage (MinIO/GCS)
4. **Notify**: Notify backend that upload is complete
5. **Poll Status**: Automatically poll document status until `ocr_status=ready` and `llm_status=ready`
6. **Navigate to Chat**: Once ready, navigate to chat screen

### Status Polling

The app automatically polls document status after upload:
- Polls every 2 seconds
- Timeout: 5 minutes
- Shows progress: "Processing document (OCR)..." → "Processing document (LLM analysis)..." → "Document ready!"

### Chat

- **Document Chat**: Chat about a specific document (`/chat/{docId}`)
- **Global Chat**: Chat across all documents (`/chat`)
- **Error Handling**: Shows friendly error messages with request_id
- **Request ID**: Automatically generated and sent with each request

### Error Handling

All API errors are parsed from the normalized backend envelope:
```json
{
  "error_code": "LLM_TIMEOUT",
  "message": "LLM service timed out",
  "details": {...},
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

Errors are displayed with:
- Friendly user message
- Request ID (with copy button)
- Error details (if available)

## API Client Features

### Request ID Support

- Automatically generates UUID4 for each request
- Sends as `X-Request-Id` header
- Includes in error responses for debugging

### Error Parsing

- Parses normalized error envelope from backend
- Converts to `ApiError` model
- Provides friendly error messages
- Includes request_id for debugging

### Status Polling

- `StatusPoller` service polls document status
- Configurable interval and timeout
- Callback for status updates
- Handles errors and timeouts

## Troubleshooting

### CORS Issues (Web)

If you see CORS errors when running against Cloud Run:

1. Ensure Cloud Run service allows your origin
2. Check backend CORS configuration
3. For development, you can use a CORS proxy (not recommended for production)

### Network Errors

- Verify Cloud Run URL is correct
- Check that services are deployed and running
- Verify network connectivity
- Check Cloud Run logs for errors

### Status Polling Timeout

If status polling times out:
- Check backend logs for processing errors
- Verify OCR/LLM services are running
- Increase timeout in `StatusPoller` if needed

### Request ID Not Showing

- Verify backend returns `request_id` in error responses
- Check that error parsing is working (see `api_client.dart`)
- Ensure `X-Request-Id` header is being sent

## Development vs Production

### Local Development

```bash
# Uses localhost:8000
flutter run -d chrome
```

### Cloud Run (Production)

```bash
# Uses Cloud Run URL
flutter run -d chrome --dart-define=CLOUD_RUN_API_BASE=https://docassis-api-xxxxx.run.app/api/v1
```

## Example: Full Upload + Chat Flow

1. **Upload Document**:
   ```
   Navigate to /upload
   Select domain and document type
   Pick PDF file
   Wait for upload and processing
   ```

2. **Automatic Navigation**:
   ```
   After processing completes, app navigates to /chat/{docId}
   ```

3. **Chat**:
   ```
   Type message
   Send
   View response
   Continue conversation
   ```

## Debugging

### View Request IDs

- Error dialogs show request_id with copy button
- Error toasts show request_id in message
- Use request_id to search backend logs

### Test Mode

Enable test mode to skip upload and go directly to chat:
```bash
flutter run -d chrome --dart-define=TEST_MODE=true
```

### Logs

Check Flutter console for:
- API request/response logs
- Error messages
- Status polling updates

## Next Steps

- Add authentication (if needed)
- Add offline support
- Add file caching
- Add retry logic for failed requests
- Add request/response logging
