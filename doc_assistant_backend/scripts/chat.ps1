# Send chat request and capture request_id
# Usage: .\chat.ps1 -ApiUrl "http://localhost:8000" -DocId "123" -Message "What is this document about?"

param(
    [Parameter(Mandatory=$false)]
    [string]$ApiUrl = "http://localhost:8000",
    
    [Parameter(Mandatory=$true)]
    [string]$DocId,
    
    [Parameter(Mandatory=$true)]
    [string]$Message
)

$ErrorActionPreference = "Stop"

Write-Host "Sending chat request" -ForegroundColor Cyan
Write-Host "  Document ID: $DocId" -ForegroundColor Gray
Write-Host "  Message: $Message" -ForegroundColor Gray

$body = @{
    messages = @(
        @{
            role = "user"
            content = $Message
        }
    )
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri "$ApiUrl/api/v1/chat/document/$DocId" `
        -Method POST `
        -Body $body `
        -ContentType "application/json" `
        -Headers @{
            "X-Request-Id" = (New-Guid).ToString()
        }
    
    # Get request_id from response headers (if available)
    $requestId = $response.PSObject.Properties['request_id'].Value
    if (-not $requestId) {
        $requestId = "unknown"
    }
    
    Write-Host "`n✅ Chat response received" -ForegroundColor Green
    Write-Host "  Request ID: $requestId" -ForegroundColor Cyan
    Write-Host "`nReply:" -ForegroundColor Yellow
    Write-Host $response.reply -ForegroundColor White
    
    Write-Host "`nUse this request_id to fetch logs:" -ForegroundColor Yellow
    Write-Host "  .\fetch_logs.ps1 -RequestId `"$requestId`"" -ForegroundColor Gray
}
catch {
    $errorResponse = $_.ErrorDetails.Message | ConvertFrom-Json -ErrorAction SilentlyContinue
    if ($errorResponse) {
        Write-Host "`n❌ Chat request failed" -ForegroundColor Red
        Write-Host "  Error Code: $($errorResponse.error_code)" -ForegroundColor Red
        Write-Host "  Message: $($errorResponse.message)" -ForegroundColor Red
        Write-Host "  Request ID: $($errorResponse.request_id)" -ForegroundColor Cyan
        
        if ($errorResponse.details) {
            Write-Host "`nDetails:" -ForegroundColor Yellow
            $errorResponse.details | ConvertTo-Json -Depth 10 | Write-Host
        }
        
        Write-Host "`nUse this request_id to fetch logs:" -ForegroundColor Yellow
        Write-Host "  .\fetch_logs.ps1 -RequestId `"$($errorResponse.request_id)`"" -ForegroundColor Gray
    }
    else {
        Write-Host "`n❌ Error: $_" -ForegroundColor Red
    }
    throw
}
