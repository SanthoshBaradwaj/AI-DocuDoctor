# Fetch logs by request_id
# Usage: .\fetch_logs.ps1 -RequestId "550e8400-e29b-41d4-a716-446655440000" -ServiceName "docassis-api"

param(
    [Parameter(Mandatory=$true)]
    [string]$RequestId,
    
    [Parameter(Mandatory=$false)]
    [string]$ServiceName = "docassis-api",
    
    [Parameter(Mandatory=$false)]
    [string]$ProjectId = "",
    
    [Parameter(Mandatory=$false)]
    [int]$Limit = 100,
    
    [Parameter(Mandatory=$false)]
    [int]$Hours = 1
)

$ErrorActionPreference = "Stop"

Write-Host "Fetching logs for request_id: $RequestId" -ForegroundColor Cyan

# Check if gcloud is available
try {
    $gcloudVersion = gcloud --version 2>&1 | Select-Object -First 1
    Write-Host "  Using gcloud: $gcloudVersion" -ForegroundColor Gray
}
catch {
    Write-Host "❌ gcloud CLI not found. Please install Google Cloud SDK." -ForegroundColor Red
    Write-Host "   For local development, use Docker logs instead:" -ForegroundColor Yellow
    Write-Host "   docker-compose logs api | Select-String `"$RequestId`"" -ForegroundColor Gray
    exit 1
}

# Build gcloud command
$filter = "jsonPayload.request_id=`"$RequestId`" OR labels.request_id=`"$RequestId`""
if ($ServiceName) {
    $filter += " AND resource.labels.service_name=`"$ServiceName`""
}

$cmd = "gcloud logging read `"$filter`" --limit $Limit --format json"
if ($Hours -gt 0) {
    $cmd += " --freshness=${Hours}h"
}
if ($ProjectId) {
    $cmd += " --project=$ProjectId"
}

Write-Host "`nExecuting: $cmd" -ForegroundColor Gray
Write-Host ""

try {
    $logs = Invoke-Expression $cmd | ConvertFrom-Json
    
    if ($logs.Count -eq 0) {
        Write-Host "No logs found for request_id: $RequestId" -ForegroundColor Yellow
        Write-Host "  Try:" -ForegroundColor Yellow
        Write-Host "    - Increasing --Hours parameter" -ForegroundColor Gray
        Write-Host "    - Checking if request_id is correct" -ForegroundColor Gray
        Write-Host "    - Verifying service name: $ServiceName" -ForegroundColor Gray
        exit 0
    }
    
    Write-Host "Found $($logs.Count) log entries`n" -ForegroundColor Green
    
    foreach ($log in $logs) {
        $timestamp = $log.timestamp
        $level = $log.severity
        $message = $log.textPayload
        if (-not $message -and $log.jsonPayload) {
            $message = $log.jsonPayload.message
        }
        $event = $log.jsonPayload.event
        $duration = $log.jsonPayload.duration_ms
        
        $color = switch ($level) {
            "ERROR" { "Red" }
            "WARNING" { "Yellow" }
            "INFO" { "Cyan" }
            "DEBUG" { "Gray" }
            default { "White" }
        }
        
        Write-Host "[$timestamp] [$level]" -ForegroundColor $color -NoNewline
        if ($event) {
            Write-Host " [$event]" -ForegroundColor Magenta -NoNewline
        }
        if ($duration) {
            Write-Host " (${duration}ms)" -ForegroundColor Gray -NoNewline
        }
        Write-Host ""
        Write-Host "  $message" -ForegroundColor White
        
        # Show extra fields
        if ($log.jsonPayload) {
            $extra = $log.jsonPayload | Get-Member -MemberType NoteProperty | 
                Where-Object { $_.Name -notin @("message", "event", "duration_ms", "request_id") } |
                Select-Object -First 5
            
            if ($extra) {
                foreach ($field in $extra) {
                    $value = $log.jsonPayload.($field.Name)
                    if ($value -and $value.ToString().Length -lt 100) {
                        Write-Host "    $($field.Name): $value" -ForegroundColor DarkGray
                    }
                }
            }
        }
        Write-Host ""
    }
    
    Write-Host "`n✅ Log fetch complete" -ForegroundColor Green
    Write-Host "  Total entries: $($logs.Count)" -ForegroundColor Cyan
}
catch {
    Write-Host "❌ Error fetching logs: $_" -ForegroundColor Red
    Write-Host "`nAlternative: Use gcloud logging console" -ForegroundColor Yellow
    Write-Host "  gcloud logging read `"$filter`" --limit $Limit --format json" -ForegroundColor Gray
    throw
}
