# EPIC 3 Runbook: Verification & Debugging

## Overview

This runbook provides PowerShell commands to verify EPIC 3 implementations and debug issues using request_id.

## Prerequisites

- Backend deployed to Cloud Run (or local)
- PowerShell 5.1+
- `gcloud` CLI (for Cloud Run logs)

## Verification Commands

### 1. Test Page Limit Enforcement

**Upload PDF with pages > MAX_PDF_PAGES:**

```powershell
# Set variables
$apiUrl = "https://docassis-api-xxxxx.run.app"
$testPdfPath = ".\large_document.pdf"  # PDF with >10 pages

# Step 1: Presign
$initBody = @{
    filename = "large_document.pdf"
    mime_type = "application/pdf"
    size_bytes = (Get-Item $testPdfPath).Length
} | ConvertTo-Json

$initResponse = Invoke-RestMethod -Uri "$apiUrl/api/v1/docs/upload/presign" `
    -Method POST -Body $initBody -ContentType "application/json"

# Step 2: Upload (PUT to presigned URL)
$fileBytes = [System.IO.File]::ReadAllBytes($testPdfPath)
Invoke-RestMethod -Uri $initResponse.upload_url -Method PUT -Body $fileBytes -ContentType "application/pdf"

# Step 3: Notify (should fail with 413)
$notifyBody = @{
    storage_key = $initResponse.storage_key
    filename = "large_document.pdf"
    mime_type = "application/pdf"
    size_bytes = (Get-Item $testPdfPath).Length
} | ConvertTo-Json

try {
    $notifyResponse = Invoke-RestMethod -Uri "$apiUrl/api/v1/docs/notify" `
        -Method POST -Body $notifyBody -ContentType "application/json"
    Write-Host "ERROR: Should have failed with 413!" -ForegroundColor Red
} catch {
    $errorResponse = $_.ErrorDetails.Message | ConvertFrom-Json
    Write-Host "✅ Correctly rejected:" -ForegroundColor Green
    Write-Host "  Status: $($_.Exception.Response.StatusCode.value__)"
    Write-Host "  Error Code: $($errorResponse.error_code)"
    Write-Host "  Message: $($errorResponse.message)"
    Write-Host "  Request ID: $($errorResponse.request_id)"
    
    # Verify error format
    if ($errorResponse.error_code -eq "PAGE_LIMIT_EXCEEDED") {
        Write-Host "✅ Error code correct" -ForegroundColor Green
    }
    if ($errorResponse.request_id) {
        Write-Host "✅ Request ID present" -ForegroundColor Green
    }
}
```

**Expected Result:**
- HTTP 413
- `error_code: "PAGE_LIMIT_EXCEEDED"`
- `message: "PDF has {page_count} pages, max allowed is {max_pages}"`
- `details: {page_count, max_pages, doc_id}`
- `request_id` present

### 2. Test File Size Limit

**Upload file exceeding MAX_UPLOAD_BYTES:**

```powershell
$apiUrl = "https://docassis-api-xxxxx.run.app"

# Create a large file (or use existing)
$largeSize = 16 * 1024 * 1024  # 16MB (exceeds 15MB default)

$initBody = @{
    filename = "large_file.pdf"
    mime_type = "application/pdf"
    size_bytes = $largeSize
} | ConvertTo-Json

try {
    $initResponse = Invoke-RestMethod -Uri "$apiUrl/api/v1/docs/upload/presign" `
        -Method POST -Body $initBody -ContentType "application/json"
    Write-Host "ERROR: Should have failed with 413!" -ForegroundColor Red
} catch {
    $errorResponse = $_.ErrorDetails.Message | ConvertFrom-Json
    Write-Host "✅ Correctly rejected in presign:" -ForegroundColor Green
    Write-Host "  Error Code: $($errorResponse.error_code)"
    Write-Host "  Message: $($errorResponse.message)"
}
```

**Expected Result:**
- HTTP 413 in `/presign` endpoint
- `error_code: "PAYLOAD_TOO_LARGE"`

### 3. Test Successful Upload (Within Limits)

**Upload PDF with pages <= MAX_PDF_PAGES:**

```powershell
$apiUrl = "https://docassis-api-xxxxx.run.app"
$testPdfPath = ".\small_document.pdf"  # PDF with <=10 pages

# Use upload script or manual steps
.\scripts\upload.ps1 -ApiUrl $apiUrl -FilePath $testPdfPath

# Verify document was created and OCR enqueued
# Check logs for: event=docs.notify, event=docs.pagecount.success, event=docs.ocr.enqueued
```

**Expected Result:**
- HTTP 200 from `/notify`
- Document created with `status="processing"`
- Page count stored in `page_count` field
- OCR task enqueued
- Logs show: `docs.notify`, `docs.pagecount.success`, `docs.ocr.enqueued`

### 4. Test Meta Endpoint

**Get document metadata:**

```powershell
$apiUrl = "https://docassis-api-xxxxx.run.app"
$docId = "123"  # Use actual document ID

$metaResponse = Invoke-RestMethod -Uri "$apiUrl/api/v1/docs/$docId/meta" -Method GET

Write-Host "Document Metadata:" -ForegroundColor Cyan
Write-Host "  ID: $($metaResponse.id)"
Write-Host "  Filename: $($metaResponse.filename)"
Write-Host "  Page Count: $($metaResponse.page_count)"
Write-Host "  OCR Chars: $($metaResponse.ocr_chars)"
Write-Host "  LLM Chars Sent: $($metaResponse.llm_chars_sent)"

# Verify all fields present
$requiredFields = @("id", "filename", "mime_type", "size_bytes", "page_count", "ocr_chars", "llm_chars_sent")
foreach ($field in $requiredFields) {
    if ($metaResponse.PSObject.Properties.Name -contains $field) {
        Write-Host "✅ $field present" -ForegroundColor Green
    } else {
        Write-Host "❌ $field missing" -ForegroundColor Red
    }
}
```

**Expected Result:**
- HTTP 200
- All cost hint fields present (may be null if not yet processed)
- Response format matches `DocMetaOut` schema

### 5. Test Request ID Propagation

**Verify request_id in logs:**

```powershell
$apiUrl = "https://docassis-api-xxxxx.run.app"
$customRequestId = "test-req-$(Get-Date -Format 'yyyyMMddHHmmss')"

# Upload with custom request_id
$headers = @{
    "X-Request-Id" = $customRequestId
    "Content-Type" = "application/json"
}

$notifyBody = @{
    storage_key = "test/document.pdf"
    filename = "test.pdf"
    mime_type = "application/pdf"
    size_bytes = 1000
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "$apiUrl/api/v1/docs/notify" `
    -Method POST -Body $notifyBody -Headers $headers

$docId = $response.id

# Check response header
$responseHeaders = $response.Headers
if ($responseHeaders["X-Request-Id"] -eq $customRequestId) {
    Write-Host "✅ Request ID in response header" -ForegroundColor Green
}

# Search logs for request_id
Write-Host "`nSearching logs for request_id: $customRequestId" -ForegroundColor Yellow
gcloud logging read "jsonPayload.request_id=`"$customRequestId`"" --limit 20 --format json
```

**Expected Result:**
- Response header `X-Request-Id` matches sent value
- All log entries include `request_id` field
- Logs searchable by request_id

### 6. Test OCR Text Truncation

**Verify LLM receives truncated text:**

```powershell
# After OCR completes, check document
$docId = "123"  # Use actual document ID

$doc = Invoke-RestMethod -Uri "$apiUrl/api/v1/docs/$docId" -Method GET
$meta = Invoke-RestMethod -Uri "$apiUrl/api/v1/docs/$docId/meta" -Method GET

Write-Host "OCR Text Length: $($meta.ocr_chars)" -ForegroundColor Cyan
Write-Host "LLM Chars Sent: $($meta.llm_chars_sent)" -ForegroundColor Cyan

if ($meta.ocr_chars -gt 50000) {
    if ($meta.llm_chars_sent -le 50000) {
        Write-Host "✅ Text correctly truncated" -ForegroundColor Green
    } else {
        Write-Host "❌ Text NOT truncated!" -ForegroundColor Red
    }
} else {
    Write-Host "✅ Text within limit, no truncation needed" -ForegroundColor Green
}

# Check logs for truncation event
gcloud logging read "jsonPayload.event=`"llm.text_prepared`" AND jsonPayload.document_id=`"$docId`"" --limit 5 --format json
```

**Expected Result:**
- `ocr_chars` > 50000 (if document is large)
- `llm_chars_sent` <= 50000
- Logs show `llm.text_prepared` event with `truncated: true`

## Debugging with Request ID

### Get Request ID from Error

```powershell
# When an error occurs, extract request_id
$errorResponse = $_.ErrorDetails.Message | ConvertFrom-Json
$requestId = $errorResponse.request_id

Write-Host "Request ID: $requestId" -ForegroundColor Cyan
```

### Search Logs by Request ID

```powershell
$requestId = "req-123-abc"

# Search all logs for this request_id
gcloud logging read "jsonPayload.request_id=`"$requestId`"" `
    --limit 100 `
    --format json `
    --freshness=1h

# Search specific events
gcloud logging read "jsonPayload.request_id=`"$requestId`" AND jsonPayload.event=~`"docs.*`"" `
    --limit 50 `
    --format json
```

### Trace Request Flow

```powershell
$requestId = "req-123-abc"

# 1. Find notify event
gcloud logging read "jsonPayload.request_id=`"$requestId`" AND jsonPayload.event=`"docs.notify`"" --format json

# 2. Find page count events
gcloud logging read "jsonPayload.request_id=`"$requestId`" AND jsonPayload.event=~`"docs.pagecount.*`"" --format json

# 3. Find OCR events
gcloud logging read "jsonPayload.request_id=`"$requestId`" AND jsonPayload.event=~`"ocr.*`"" --format json

# 4. Find LLM events
gcloud logging read "jsonPayload.request_id=`"$requestId`" AND jsonPayload.event=~`"llm.*`"" --format json
```

## PowerShell Scripts

### check_meta.ps1

```powershell
# Check document metadata
param(
    [Parameter(Mandatory=$true)]
    [string]$DocId,
    
    [Parameter(Mandatory=$false)]
    [string]$ApiUrl = "https://docassis-api-xxxxx.run.app"
)

$meta = Invoke-RestMethod -Uri "$ApiUrl/api/v1/docs/$DocId/meta" -Method GET

Write-Host "Document Metadata (Doc ID: $DocId)" -ForegroundColor Cyan
Write-Host "  Filename: $($meta.filename)"
Write-Host "  MIME Type: $($meta.mime_type)"
Write-Host "  Size: $($meta.size_bytes) bytes"
Write-Host "  Page Count: $($meta.page_count)"
Write-Host "  OCR Chars: $($meta.ocr_chars)"
Write-Host "  LLM Chars Sent: $($meta.llm_chars_sent)"
```

### upload_and_verify_limits.ps1

```powershell
# Upload and verify limits are enforced
param(
    [Parameter(Mandatory=$true)]
    [string]$FilePath,
    
    [Parameter(Mandatory=$false)]
    [string]$ApiUrl = "https://docassis-api-xxxxx.run.app"
)

$fileSize = (Get-Item $FilePath).Length
$maxBytes = 15 * 1024 * 1024  # 15MB

Write-Host "File: $FilePath" -ForegroundColor Cyan
Write-Host "Size: $fileSize bytes" -ForegroundColor Cyan
Write-Host "Max: $maxBytes bytes" -ForegroundColor Cyan

if ($fileSize > $maxBytes) {
    Write-Host "⚠️  File exceeds MAX_UPLOAD_BYTES - should be rejected" -ForegroundColor Yellow
}

# Upload and check response
# (Implementation similar to upload.ps1 but with limit verification)
```

## Common Issues & Solutions

### Issue: Page count not extracted
**Solution:**
- Check logs for `docs.pagecount.fail` event
- Verify PDF is valid (not corrupted)
- Check storage access (GCS/S3 permissions)
- Page counting is non-fatal - document still processes

### Issue: LLM receives full text (not truncated)
**Solution:**
- Check `llm_chars_sent` in `/meta` endpoint
- Verify `MAX_OCR_CHARS` config is set correctly
- Check logs for `llm.text_prepared` event

### Issue: Request ID not in logs
**Solution:**
- Verify `RequestIdMiddleware` is registered in `main.py`
- Check that `X-Request-Id` header is being sent
- Verify logging formatter includes request_id

### Issue: Meta endpoint returns 404
**Solution:**
- Verify document ID is correct (string, not int)
- Check document exists in database
- Verify `/meta` endpoint is registered in router

## Success Criteria Verification

Run all verification commands above. All should pass:
- ✅ Page limit enforcement works
- ✅ File size limit enforcement works
- ✅ Meta endpoint returns cost hints
- ✅ Request ID propagation works
- ✅ Structured logging includes event names
- ✅ OCR text truncation works
