# Epic 2 Chunk #3: MVP Fixes - Implementation Summary

## Status: ✅ COMPLETE

## Issues Fixed

### 1. FilePicker Path Access on Web ✅
**Problem**: Accessing `f.path` on Flutter web throws an exception.

**Solution**:
- Added `kIsWeb` check before accessing `f.path`
- On web: Only use `f.bytes` (never access `f.path`)
- On mobile/desktop: Use `f.path` for file upload
- Updated `upload_page.dart` to handle both cases

**Files Changed**:
- `lib/features/upload/upload_page.dart`

### 2. GCS Signed URL Upload Format ✅
**Problem**: GCS signed URLs require HTTP PUT with raw bytes and Content-Type header, NOT multipart/form-data POST.

**Solution**:
- Created `uploadBytesToPresigned()` method for web (bytes)
- Updated `uploadToPresigned()` method for mobile (file path)
- Both methods use HTTP PUT with raw bytes
- Set Content-Type header correctly
- Removed multipart/form-data logic

**Files Changed**:
- `lib/services/api_client.dart`
- `lib/features/upload/upload_page.dart`

### 3. docId String Type ✅
**Problem**: Backend returns string IDs, but Flutter was using `int` throughout.

**Solution**:
- Changed all `docId` from `int` to `String`
- Updated models: `Doc.id`, `DocDetail.id`, `DocStatus.id`
- Updated API client methods to accept `String` docId
- Updated routes to use string IDs (no `int.parse()`)
- Updated chat controllers to use `String` docId
- Updated all UI components

**Files Changed**:
- `lib/models/doc.dart`
- `lib/models/doc_status.dart`
- `lib/services/api_client.dart`
- `lib/services/status_poller.dart`
- `lib/routing/app_router.dart`
- `lib/features/docs/doc_detail_page.dart`
- `lib/features/chat/chat_page.dart`
- `lib/features/chat/chat_controller.dart`
- `lib/features/chat/doc_chat_widget.dart`
- `lib/config.dart` (test mode)

### 4. Dio baseUrl Configuration ✅
**Problem**: Double-prefixing `/api/v1` causing connection errors.

**Solution**:
- Updated `kApiBase` to NOT include `/api/v1`
- All API routes explicitly include `/api/v1` prefix
- Added logic to strip `/api/v1` if present in Cloud Run URL
- Added `debugPrint` to log baseUrl and requests
- Added request logging in interceptor

**Files Changed**:
- `lib/config.dart`
- `lib/services/api_client.dart`

### 5. Diagnostics Widget ✅
**New Feature**: Added diagnostics widget for debugging.

**Features**:
- Shows API base URL
- Shows Cloud Run status
- Shows test mode status
- Copy buttons for easy sharing
- Accessible from Settings page

**Files Created**:
- `lib/widgets/api_diagnostics.dart`

**Files Modified**:
- `lib/features/settings/settings_page.dart`

### 6. Test Checklist ✅
**Created**: Comprehensive test checklist for MVP validation.

**Files Created**:
- `TEST_CHECKLIST.md`

## Key Changes Summary

### Upload Flow
```dart
// Web: Use bytes, never access f.path
if (kIsWeb) {
  await api.uploadBytesToPresigned(
    url: uploadUrl,
    bytes: f.bytes!,
    contentType: mimeType,
  );
} else {
  // Mobile: Use file path
  await api.uploadToPresigned(
    url: uploadUrl,
    filePath: f.path!,
    contentType: mimeType,
  );
}
```

### GCS Upload (HTTP PUT)
```dart
// GCS signed URLs require HTTP PUT with raw bytes
return miniDio.put(
  uploadUrl,
  data: bytes, // Raw bytes, not FormData
  options: Options(
    contentType: contentType ?? 'application/octet-stream',
  ),
);
```

### docId String Type
```dart
// All docId are now String
final String docId; // Not int
await api.chatWithDocument(docId, messages); // docId is String
```

### baseUrl Configuration
```dart
// baseUrl should NOT include /api/v1
const String kWebApiBase = 'http://localhost:8000'; // No /api/v1

// Routes explicitly include /api/v1
await _dio.get('/api/v1/docs/$id');
```

## Testing

Run the test checklist in `TEST_CHECKLIST.md`:
1. Upload Flow
2. Status Polling
3. Chat Flow
4. Error Handling
5. Diagnostics Widget
6. FilePicker Web Compatibility
7. GCS Upload Format
8. docId String Type

## Verification Commands

### Check baseUrl
```dart
// In Flutter app, open Settings > Show API Diagnostics
// Should show baseUrl without /api/v1 suffix
```

### Check Upload Format
```bash
# In browser DevTools > Network tab
# Upload a file and check the request:
# - Method: PUT (not POST)
# - Content-Type: application/pdf (or correct mime type)
# - Body: Raw bytes (not multipart/form-data)
```

### Check docId Type
```dart
// All docId should be String
final docId = '123'; // String, not int
context.go('/chat/$docId'); // Works with string
```

## Files Changed

1. `lib/config.dart` - Fixed baseUrl, test mode docId
2. `lib/services/api_client.dart` - Fixed upload methods, docId types, baseUrl routes
3. `lib/models/doc.dart` - Changed id to String
4. `lib/models/doc_status.dart` - Changed id to String
5. `lib/services/status_poller.dart` - Changed docId to String
6. `lib/features/upload/upload_page.dart` - Fixed web path access, GCS upload
7. `lib/routing/app_router.dart` - Changed docId to String
8. `lib/features/docs/doc_detail_page.dart` - Changed docId to String
9. `lib/features/chat/chat_page.dart` - Changed docId to String
10. `lib/features/chat/chat_controller.dart` - Changed docId to String
11. `lib/features/chat/doc_chat_widget.dart` - Changed docId to String
12. `lib/widgets/api_diagnostics.dart` - NEW: Diagnostics widget
13. `lib/features/settings/settings_page.dart` - Added diagnostics button
14. `TEST_CHECKLIST.md` - NEW: Test checklist

## Next Steps

1. Run test checklist
2. Verify all uploads work (web + mobile)
3. Verify chat works with string docIds
4. Check diagnostics widget shows correct baseUrl
5. Verify GCS uploads use PUT with raw bytes
