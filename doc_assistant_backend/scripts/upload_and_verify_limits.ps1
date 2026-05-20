# Upload document and verify limits are enforced
# Usage: .\upload_and_verify_limits.ps1 -FilePath ".\test.pdf" -ApiUrl "https://docassis-api-xxxxx.run.app"

param(
    [Parameter(Mandatory=$true)]
    [string]$FilePath,
    
    [Parameter(Mandatory=$false)]
    [string]$ApiUrl = "https://docassis-api-xxxxx.run.app"
)

$ErrorActionPreference = "Stop"

Write-Host "Uploading and verifying limits: $FilePath" -ForegroundColor Cyan

$fileSize = (Get-Item $FilePath).Length
$maxBytes = 15 * 1024 * 1024  # 15MB default

Write-Host "`nFile Info:" -ForegroundColor Yellow
Write-Host "  Size: $fileSize bytes ($([math]::Round($fileSize / 1MB, 2)) MB)" -ForegroundColor White
Write-Host "  Max: $maxBytes bytes ($([math]::Round($maxBytes / 1MB, 2)) MB)" -ForegroundColor White

if ($fileSize > $maxBytes) {
    Write-Host "`n⚠️  File exceeds MAX_UPLOAD_BYTES - should be rejected" -ForegroundColor Yellow
}

# Step 1: Presign
Write-Host "`n1. Initializing upload..." -ForegroundColor Yellow
$initBody = @{
    filename = Split-Path -Leaf $FilePath
    mime_type = "application/pdf"
    size_bytes = $fileSize
} | ConvertTo-Json

try {
    $initResponse = Invoke-RestMethod -Uri "$ApiUrl/api/v1/docs/upload/presign" `
        -Method POST -Body $initBody -ContentType "application/json"
    Write-Host "  ✅ Presign successful" -ForegroundColor Green
} catch {
    $errorResponse = $_.ErrorDetails.Message | ConvertFrom-Json -ErrorAction SilentlyContinue
    if ($errorResponse -and $errorResponse.error_code -eq "PAYLOAD_TOO_LARGE") {
        Write-Host "  ✅ Correctly rejected at presign (size limit)" -ForegroundColor Green
        exit 0
    }
    throw
}

# Step 2: Upload
Write-Host "`n2. Uploading file..." -ForegroundColor Yellow
$fileBytes = [System.IO.File]::ReadAllBytes($FilePath)
Invoke-RestMethod -Uri $initResponse.upload_url -Method PUT -Body $fileBytes -ContentType "application/pdf"
Write-Host "  ✅ Upload complete" -ForegroundColor Green

# Step 3: Notify
Write-Host "`n3. Notifying backend..." -ForegroundColor Yellow
$notifyBody = @{
    storage_key = $initResponse.storage_key
    filename = Split-Path -Leaf $FilePath
    mime_type = "application/pdf"
    size_bytes = $fileSize
} | ConvertTo-Json

try {
    $notifyResponse = Invoke-RestMethod -Uri "$ApiUrl/api/v1/docs/notify" `
        -Method POST -Body $notifyBody -ContentType "application/json"
    
    $docId = $notifyResponse.id
    Write-Host "  ✅ Document created: $docId" -ForegroundColor Green
    
    # Wait a moment for page counting
    Start-Sleep -Seconds 2
    
    # Check meta endpoint
    Write-Host "`n4. Checking metadata..." -ForegroundColor Yellow
    $meta = Invoke-RestMethod -Uri "$ApiUrl/api/v1/docs/$docId/meta" -Method GET
    
    Write-Host "  Page Count: $($meta.page_count)" -ForegroundColor $(if ($meta.page_count) { "Green" } else { "Gray" })
    Write-Host "  OCR Chars: $($meta.ocr_chars)" -ForegroundColor $(if ($meta.ocr_chars) { "Green" } else { "Gray" })
    Write-Host "  LLM Chars Sent: $($meta.llm_chars_sent)" -ForegroundColor $(if ($meta.llm_chars_sent) { "Green" } else { "Gray" })
    
    Write-Host "`n✅ Upload and verification complete!" -ForegroundColor Green
    Write-Host "  Document ID: $docId" -ForegroundColor Cyan
    Write-Host "  Request ID: $($notifyResponse.request_id)" -ForegroundColor Cyan
    
} catch {
    $errorResponse = $_.ErrorDetails.Message | ConvertFrom-Json -ErrorAction SilentlyContinue
    if ($errorResponse) {
        Write-Host "`nError Response:" -ForegroundColor Red
        Write-Host "  Error Code: $($errorResponse.error_code)" -ForegroundColor Red
        Write-Host "  Message: $($errorResponse.message)" -ForegroundColor Red
        Write-Host "  Request ID: $($errorResponse.request_id)" -ForegroundColor Cyan
        
        if ($errorResponse.error_code -eq "PAGE_LIMIT_EXCEEDED") {
            Write-Host "`n✅ Correctly rejected (page limit)" -ForegroundColor Green
        } elseif ($errorResponse.error_code -eq "PAYLOAD_TOO_LARGE") {
            Write-Host "`n✅ Correctly rejected (size limit)" -ForegroundColor Green
        } else {
            Write-Host "`n❌ Unexpected error" -ForegroundColor Red
            throw
        }
    } else {
        throw
    }
}
