# Poll document status until ready or error
# Usage: .\poll_status.ps1 -ApiUrl "http://localhost:8000" -DocId "123"

param(
    [Parameter(Mandatory=$false)]
    [string]$ApiUrl = "http://localhost:8000",
    
    [Parameter(Mandatory=$true)]
    [string]$DocId,
    
    [Parameter(Mandatory=$false)]
    [int]$IntervalSeconds = 2,
    
    [Parameter(Mandatory=$false)]
    [int]$MaxAttempts = 60
)

$ErrorActionPreference = "Stop"

Write-Host "Polling document status: $DocId" -ForegroundColor Cyan
Write-Host "  Interval: $IntervalSeconds seconds" -ForegroundColor Gray
Write-Host "  Max attempts: $MaxAttempts" -ForegroundColor Gray

$attempt = 0
$isReady = $false

while (-not $isReady -and $attempt -lt $MaxAttempts) {
    $attempt++
    
    try {
        $response = Invoke-RestMethod -Uri "$ApiUrl/api/v1/docs/$DocId/status" `
            -Method GET
        
        $status = $response.status
        $ocrStatus = $response.ocr_status
        $llmStatus = $response.llm_status
        $lastError = $response.last_error
        
        Write-Host "`nAttempt $attempt/$MaxAttempts" -ForegroundColor Yellow
        Write-Host "  Status: $status" -ForegroundColor $(if ($status -eq "ready") { "Green" } else { "Yellow" })
        Write-Host "  OCR Status: $ocrStatus" -ForegroundColor $(if ($ocrStatus -eq "ready") { "Green" } elseif ($ocrStatus -eq "error") { "Red" } else { "Yellow" })
        Write-Host "  LLM Status: $llmStatus" -ForegroundColor $(if ($llmStatus -eq "ready") { "Green" } elseif ($llmStatus -eq "error") { "Red" } else { "Yellow" })
        
        if ($lastError) {
            Write-Host "  Last Error: $lastError" -ForegroundColor Red
        }
        
        # Check if ready
        if ($status -eq "ready" -and $ocrStatus -eq "ready") {
            $isReady = $true
            Write-Host "`n✅ Document is ready!" -ForegroundColor Green
            Write-Host "  Chat available: $($llmStatus -eq 'ready')" -ForegroundColor Cyan
            break
        }
        
        # Check if error
        if ($status -eq "error" -or $ocrStatus -eq "error") {
            Write-Host "`n❌ Document processing failed" -ForegroundColor Red
            if ($lastError) {
                Write-Host "  Error: $lastError" -ForegroundColor Red
            }
            break
        }
        
        # Wait before next attempt
        if (-not $isReady) {
            Start-Sleep -Seconds $IntervalSeconds
        }
    }
    catch {
        Write-Host "`n❌ Error polling status: $_" -ForegroundColor Red
        break
    }
}

if (-not $isReady -and $attempt -ge $MaxAttempts) {
    Write-Host "`n⏱️  Timeout: Document not ready after $MaxAttempts attempts" -ForegroundColor Yellow
}
