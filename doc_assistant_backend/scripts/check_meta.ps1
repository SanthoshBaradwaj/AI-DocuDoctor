# Check document metadata (cost hints)
# Usage: .\check_meta.ps1 -DocId "123" -ApiUrl "https://docassis-api-xxxxx.run.app"

param(
    [Parameter(Mandatory=$true)]
    [string]$DocId,
    
    [Parameter(Mandatory=$false)]
    [string]$ApiUrl = "https://docassis-api-xxxxx.run.app"
)

$ErrorActionPreference = "Stop"

Write-Host "Fetching document metadata: $DocId" -ForegroundColor Cyan

try {
    $meta = Invoke-RestMethod -Uri "$ApiUrl/api/v1/docs/$DocId/meta" -Method GET
    
    Write-Host "`nDocument Metadata" -ForegroundColor Green
    Write-Host "  ID: $($meta.id)" -ForegroundColor White
    Write-Host "  Filename: $($meta.filename)" -ForegroundColor White
    Write-Host "  MIME Type: $($meta.mime_type)" -ForegroundColor White
    Write-Host "  Size: $($meta.size_bytes) bytes" -ForegroundColor White
    if ($meta.domain) {
        Write-Host "  Domain: $($meta.domain)" -ForegroundColor White
    }
    if ($meta.doc_type) {
        Write-Host "  Doc Type: $($meta.doc_type)" -ForegroundColor White
    }
    
    Write-Host "`nCost Hints" -ForegroundColor Yellow
    if ($meta.page_count) {
        Write-Host "  Page Count: $($meta.page_count)" -ForegroundColor White
    } else {
        Write-Host "  Page Count: (not set)" -ForegroundColor Gray
    }
    if ($meta.ocr_chars) {
        Write-Host "  OCR Chars: $($meta.ocr_chars)" -ForegroundColor White
    } else {
        Write-Host "  OCR Chars: (not set)" -ForegroundColor Gray
    }
    if ($meta.llm_chars_sent) {
        Write-Host "  LLM Chars Sent: $($meta.llm_chars_sent)" -ForegroundColor White
    } else {
        Write-Host "  LLM Chars Sent: (not set)" -ForegroundColor Gray
    }
    
    # Verify truncation if OCR chars > MAX_OCR_CHARS
    $maxOcrChars = 50000
    if ($meta.ocr_chars -and $meta.ocr_chars -gt $maxOcrChars) {
        if ($meta.llm_chars_sent -and $meta.llm_chars_sent -le $maxOcrChars) {
            Write-Host "`n✅ Text correctly truncated" -ForegroundColor Green
        } else {
            Write-Host "`n❌ Text NOT truncated!" -ForegroundColor Red
        }
    }
    
} catch {
    $errorResponse = $_.ErrorDetails.Message | ConvertFrom-Json -ErrorAction SilentlyContinue
    if ($errorResponse) {
        Write-Host "`n❌ Error: $($errorResponse.error_code)" -ForegroundColor Red
        Write-Host "  Message: $($errorResponse.message)" -ForegroundColor Red
        Write-Host "  Request ID: $($errorResponse.request_id)" -ForegroundColor Cyan
    } else {
        Write-Host "`n❌ Error: $_" -ForegroundColor Red
    }
    throw
}
