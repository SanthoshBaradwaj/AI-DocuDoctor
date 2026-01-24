# Upload a document and get request_id
# Usage: .\upload.ps1 -ApiUrl "http://localhost:8000" -FilePath ".\sample.pdf"

param(
    [Parameter(Mandatory=$false)]
    [string]$ApiUrl = "http://localhost:8000",
    
    [Parameter(Mandatory=$true)]
    [string]$FilePath
)

$ErrorActionPreference = "Stop"

Write-Host "Uploading document: $FilePath" -ForegroundColor Cyan

# Step 1: Initialize upload
Write-Host "`n1. Initializing upload..." -ForegroundColor Yellow
$initBody = @{
    filename = Split-Path -Leaf $FilePath
    mime_type = "application/pdf"
    size_bytes = (Get-Item $FilePath).Length
} | ConvertTo-Json

$initResponse = Invoke-RestMethod -Uri "$ApiUrl/api/v1/docs/upload/presign" `
    -Method POST `
    -Body $initBody `
    -ContentType "application/json"

$requestId = $initResponse.PSObject.Properties['request_id'].Value
if (-not $requestId) {
    $requestId = "unknown"
}

Write-Host "  Request ID: $requestId" -ForegroundColor Green
Write-Host "  Storage Key: $($initResponse.storage_key)" -ForegroundColor Gray
Write-Host "  Upload URL: $($initResponse.upload_url)" -ForegroundColor Gray

# Step 2: Upload file
Write-Host "`n2. Uploading file..." -ForegroundColor Yellow
$fileBytes = [System.IO.File]::ReadAllBytes($FilePath)
$uploadResponse = Invoke-RestMethod -Uri $initResponse.upload_url `
    -Method PUT `
    -Body $fileBytes `
    -ContentType "application/pdf"

Write-Host "  Upload complete" -ForegroundColor Green

# Step 3: Notify backend
Write-Host "`n3. Notifying backend..." -ForegroundColor Yellow
$notifyBody = @{
    storage_key = $initResponse.storage_key
    filename = Split-Path -Leaf $FilePath
    mime_type = "application/pdf"
    size_bytes = (Get-Item $FilePath).Length
} | ConvertTo-Json

$notifyResponse = Invoke-RestMethod -Uri "$ApiUrl/api/v1/docs/notify" `
    -Method POST `
    -Body $notifyBody `
    -ContentType "application/json"

$docId = $notifyResponse.id
Write-Host "  Document ID: $docId" -ForegroundColor Green
Write-Host "  Status: $($notifyResponse.status)" -ForegroundColor Gray
Write-Host "  OCR Status: $($notifyResponse.ocr_status)" -ForegroundColor Gray
Write-Host "  LLM Status: $($notifyResponse.llm_status)" -ForegroundColor Gray

Write-Host "`n✅ Upload complete!" -ForegroundColor Green
Write-Host "  Document ID: $docId" -ForegroundColor Cyan
Write-Host "  Request ID: $requestId" -ForegroundColor Cyan
Write-Host "`nUse this request_id to fetch logs:" -ForegroundColor Yellow
Write-Host "  .\fetch_logs.ps1 -RequestId `"$requestId`"" -ForegroundColor Gray
