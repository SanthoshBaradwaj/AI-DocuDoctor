# Flutter MVP Test Checklist

## Prerequisites
- [ ] Backend deployed to Cloud Run (or local Docker)
- [ ] Flutter app configured with Cloud Run URL (or localhost)
- [ ] Browser console open (F12) for debugging

## Test 1: Upload Flow

### Steps:
1. [ ] Navigate to Upload page
2. [ ] Select domain (e.g., IDENTITY)
3. [ ] Select document type (e.g., PASSPORT)
4. [ ] Click "Pick & Upload"
5. [ ] Select a PDF file
6. [ ] Verify progress indicators:
   - [ ] "Initializing upload..."
   - [ ] "Uploading to storage..." (progress bar)
   - [ ] "Notifying backend..."
   - [ ] "Processing document (OCR)..." (status polling)
   - [ ] "Processing document (LLM analysis)..." (if applicable)
   - [ ] "Document ready!"

### Expected Results:
- [ ] Upload completes without errors
- [ ] Status polling works (shows progress)
- [ ] Automatically navigates to chat screen after ready
- [ ] Document ID is displayed correctly (string, not int)

### Debug Checks:
- [ ] Check browser console for API calls
- [ ] Verify baseUrl is correct (no double /api/v1)
- [ ] Verify request_id is sent in headers
- [ ] Check network tab: upload should be HTTP PUT (not POST multipart)

## Test 2: Status Polling

### Steps:
1. [ ] Upload a document (from Test 1)
2. [ ] Watch status updates in UI
3. [ ] Verify status transitions:
   - [ ] OCR: pending → processing → ready
   - [ ] LLM: pending → ready (when OCR completes)

### Expected Results:
- [ ] Status updates every 2 seconds
- [ ] UI shows current processing step
- [ ] Polling stops when ready
- [ ] No timeout errors (within 5 minutes)

### Debug Checks:
- [ ] Check console logs for polling requests
- [ ] Verify `/api/v1/docs/{docId}/status` endpoint is called
- [ ] Verify request_id is included in logs

## Test 3: Chat Flow

### Steps:
1. [ ] Navigate to chat (should auto-navigate after upload)
2. [ ] Type a message (e.g., "What is this document about?")
3. [ ] Click "Send"
4. [ ] Wait for response

### Expected Results:
- [ ] Message appears in chat
- [ ] Response received from backend
- [ ] No errors displayed
- [ ] Request ID included in error messages (if error occurs)

### Debug Checks:
- [ ] Check console for chat API call
- [ ] Verify endpoint: `/api/v1/chat/document/{docId}`
- [ ] Verify request_id header is sent
- [ ] Check response format matches expected schema

## Test 4: Error Handling

### Steps:
1. [ ] Try to chat with non-existent document ID
2. [ ] Check error dialog/toast
3. [ ] Verify request_id is shown
4. [ ] Test copy button for request_id

### Expected Results:
- [ ] Error dialog shows friendly message
- [ ] Request ID is displayed
- [ ] Copy button works
- [ ] Error format matches: `{error_code, message, details, request_id}`

## Test 5: Diagnostics Widget

### Steps:
1. [ ] Open diagnostics widget (if available in settings)
2. [ ] Check displayed information:
   - [ ] Base URL
   - [ ] Cloud Run status
   - [ ] Test mode status
3. [ ] Test copy functionality

### Expected Results:
- [ ] Base URL is correct (no /api/v1 suffix)
- [ ] Cloud Run status reflects environment
- [ ] Copy buttons work

## Test 6: FilePicker Web Compatibility

### Steps:
1. [ ] Run app in Chrome (web)
2. [ ] Try to upload a file
3. [ ] Verify no errors about `f.path` access

### Expected Results:
- [ ] Upload works on web
- [ ] No exceptions about path access
- [ ] Uses bytes for upload (not file path)

## Test 7: GCS Upload Format

### Steps:
1. [ ] Upload a file
2. [ ] Check network tab in browser
3. [ ] Inspect upload request

### Expected Results:
- [ ] HTTP method: PUT (not POST)
- [ ] Content-Type header is set correctly
- [ ] Request body is raw bytes (not multipart/form-data)
- [ ] No form fields in request

## Test 8: docId String Type

### Steps:
1. [ ] Upload a document
2. [ ] Check document ID in UI
3. [ ] Navigate to chat
4. [ ] Check URL parameters

### Expected Results:
- [ ] Document ID is string (not int)
- [ ] No int.parse() errors
- [ ] Routes work with string IDs
- [ ] API calls use string IDs

## Common Issues & Solutions

### Issue: Double /api/v1 in URL
**Solution**: Check `kApiBase` - should NOT include /api/v1

### Issue: FilePicker path error on web
**Solution**: Use `kIsWeb` check, never access `f.path` on web

### Issue: Upload fails with 400/403
**Solution**: Verify upload is HTTP PUT with raw bytes, not multipart POST

### Issue: docId type errors
**Solution**: Ensure all docId variables are String, not int

### Issue: Connection errors
**Solution**: 
- Check baseUrl in diagnostics widget
- Verify Cloud Run URL is correct
- Check CORS settings on backend

## Success Criteria

All tests pass:
- [ ] Upload works (web + mobile)
- [ ] Status polling works
- [ ] Chat works
- [ ] Error handling works
- [ ] No type errors
- [ ] No path access errors on web
- [ ] GCS upload uses PUT with raw bytes
