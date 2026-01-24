# Epic 2 Chunk #3: Flutter UI Integration - Implementation Summary

## Status: ✅ COMPLETE

## Overview

This implementation enables Flutter to upload PDFs, poll document status, and chat with documents against Cloud Run backend services.

## Changes Made

### 1. API Client Layer (`lib/services/api_client.dart`)

**Enhanced Features:**
- ✅ Request ID support: Automatically generates UUID4 and sends as `X-Request-Id` header
- ✅ Error parsing: Parses normalized backend error envelope `{error_code, message, details, request_id}`
- ✅ Error interceptor: Converts DioException to ApiError when backend returns normalized errors
- ✅ Status polling endpoint: `fetchDocStatus(int id)` for polling document status

**Key Methods:**
- `chatWithDocument()`: Throws `ApiError` instead of generic exceptions
- `chatGlobal()`: Throws `ApiError` instead of generic exceptions
- `fetchDocStatus()`: NEW - Get document status for polling

### 2. Error Models (`lib/models/api_error.dart`)

**New Model:**
- `ApiError`: Matches backend normalized error envelope
- `friendlyMessage`: Maps error codes to user-friendly messages
- Includes: `errorCode`, `message`, `details`, `requestId`

**Error Code Mappings:**
- `LLM_TIMEOUT` → "The AI service took too long to respond..."
- `LLM_UNREACHABLE` → "Unable to reach the AI service..."
- `VALIDATION_ERROR` → "Invalid input..."
- And more...

### 3. Status Polling (`lib/services/status_poller.dart`)

**New Service:**
- `StatusPoller`: Polls document status until ready
- Configurable interval (default: 2 seconds)
- Configurable timeout (default: 5 minutes)
- Status update callback for UI updates
- Handles errors and timeouts gracefully

### 4. Document Models (`lib/models/doc.dart`)

**Enhanced:**
- Added `ocrStatus` and `llmStatus` fields
- Added `isChatAvailable` getter: `ocrStatus == 'ready' && llmStatus == 'ready'`
- Added `isProcessing` getter: Checks if document is still processing
- Updated `DocDetail` to include status fields

**New Model:**
- `DocStatus` (`lib/models/doc_status.dart`): Status response model with helpers

### 5. Upload Flow (`lib/features/upload/upload_page.dart`)

**Enhanced Flow:**
1. Pick file (PDF)
2. POST `/api/v1/docs/upload/presign`
3. PUT to `upload_url` with file bytes
4. POST `/api/v1/docs/notify`
5. **NEW**: Poll status until `ocr_status=ready` and `llm_status=ready`
6. Navigate to `/chat/{docId}`

**Status Polling:**
- Shows progress: "Processing document (OCR)..." → "Processing document (LLM analysis)..." → "Document ready!"
- Handles errors with `ErrorDialog`
- Navigates to chat once ready

### 6. Chat Screen (`lib/features/chat/`)

**Updated:**
- `chat_controller.dart`: Handles `ApiError` exceptions
- Shows friendly error messages in chat
- Includes request_id in error messages
- Updated both document and global chat

**Error Handling:**
- Catches `ApiError` and displays friendly message
- Includes request_id for debugging
- Falls back to generic error message if parsing fails

### 7. Error UI (`lib/widgets/error_dialog.dart`)

**New Widgets:**
- `ErrorDialog`: Modal dialog showing error with request_id copy button
- `ErrorToast`: Snackbar showing error with request_id

**Features:**
- Shows friendly error message
- Displays request_id with copy button
- Shows error details (if available)
- Copy to clipboard functionality

### 8. Configuration (`lib/config.dart`)

**Enhanced:**
- `kCloudRunApiBase`: Cloud Run URL from environment variable
- `kApiBase`: Priority: Cloud Run > Web > Default
- `kTestMode`: Test mode flag for debugging
- `kTestDocId`: Hardcoded document ID for test mode

**Usage:**
```bash
flutter run -d chrome --dart-define=CLOUD_RUN_API_BASE=https://docassis-api-xxxxx.run.app/api/v1
```

### 9. Routing (`lib/routing/app_router.dart`)

**Added Route:**
- `/chat/:docId`: Direct chat route with document ID in path
- Supports test mode navigation

### 10. Test Mode (`lib/features/chat/test_chat_page.dart`)

**New Feature:**
- Test mode allows opening chat directly with hardcoded document ID
- Useful for debugging without uploading

**Enable:**
```bash
flutter run -d chrome --dart-define=TEST_MODE=true
```

## Files Created/Modified

### New Files:
1. `lib/models/api_error.dart` - Error model
2. `lib/models/doc_status.dart` - Status model
3. `lib/services/status_poller.dart` - Status polling service
4. `lib/widgets/error_dialog.dart` - Error UI widgets
5. `lib/features/chat/test_chat_page.dart` - Test mode page
6. `README_CLOUD_RUN.md` - Cloud Run integration guide

### Modified Files:
1. `lib/services/api_client.dart` - Enhanced with error handling and request_id
2. `lib/models/doc.dart` - Added status fields and helpers
3. `lib/features/upload/upload_page.dart` - Added status polling
4. `lib/features/chat/chat_controller.dart` - Enhanced error handling
5. `lib/config.dart` - Added Cloud Run and test mode config
6. `lib/routing/app_router.dart` - Added chat route with docId

## Usage Examples

### Upload + Poll + Chat Flow

```dart
// 1. Upload file
final api = ApiClient();
final initResult = await api.initUpload(...);
// Upload file...
final doc = await api.notifyUploaded(...);

// 2. Poll status
final poller = StatusPoller(api);
await poller.pollUntilReady(
  docId: doc.id,
  onStatusUpdate: (status) {
    // Update UI
  },
);

// 3. Chat
final response = await api.chatWithDocument(
  doc.id,
  [ChatMessage('user', 'What is this document?')],
);
```

### Error Handling

```dart
try {
  final response = await api.chatWithDocument(docId, messages);
} on ApiError catch (e) {
  ErrorDialog.show(context, e);
  // Or
  ErrorToast.show(context, e);
}
```

### Test Mode

```bash
# Enable test mode
flutter run -d chrome --dart-define=TEST_MODE=true

# Navigate to /chat - automatically uses doc ID 1
```

## Testing

### Manual Testing Checklist

- [ ] Upload PDF and verify status polling works
- [ ] Verify error dialog shows request_id with copy button
- [ ] Test chat with document and verify error handling
- [ ] Test Cloud Run URL configuration
- [ ] Test test mode functionality
- [ ] Verify request_id is sent in headers
- [ ] Verify error parsing from backend responses

### Cloud Run Testing

1. Deploy backend to Cloud Run
2. Set `CLOUD_RUN_API_BASE` environment variable
3. Run Flutter app
4. Upload document
5. Verify status polling works
6. Test chat functionality
7. Verify error handling with real backend errors

## Next Steps

- Add authentication (if needed)
- Add offline support
- Add request/response logging
- Add retry logic for failed requests
- Add file caching
- Add progress indicators for chat
- Add streaming support (when backend supports SSE)

## Notes

- All API errors are now parsed from normalized backend envelope
- Request ID is automatically generated and included in all requests
- Status polling is automatic after upload
- Error UI provides copy button for request_id
- Test mode allows quick debugging without upload flow
