# ===== Config =====
$API  = "http://localhost:8000"

# CHANGE THIS to your test file
$File = "C:\Users\Santhosh Baradwaj\Documents\test.txt"

function Ok($m){ Write-Host "✅ $m" -ForegroundColor Green }
function Info($m){ Write-Host "➜ $m" -ForegroundColor Cyan }
function Warn($m){ Write-Host "⚠ $m" -ForegroundColor Yellow }
function Fail($m){ Write-Host "✖ $m" -ForegroundColor Red }

if (!(Test-Path $File)) { Fail "File not found: $File"; exit 1 }
$size = (Get-Item $File).Length
$leaf = (Split-Path $File -Leaf)
Info "Using file: $File ($size bytes)"

# Step 1: presign
Info "Requesting presigned POST from API..."
try { $presign = Invoke-RestMethod -Method Post -Uri "$API/docs/upload/presign" }
catch { Fail "Presign failed. $_"; exit 1 }
if (-not $presign.url -or -not $presign.fields -or -not $presign.key) {
  Fail "Presign response missing fields: $($presign | ConvertTo-Json -Depth 6)"
  exit 1
}
Ok "Presign ok: key = $($presign.key)"

# Fix presign URL for host access (minio -> localhost)
$UploadUrl = $presign.url
if ($UploadUrl -match "://minio:9000") {
  $UploadUrl = $UploadUrl -replace "minio:9000","localhost:9000"
  Info "Rewriting upload URL for host: $UploadUrl"
}

# Step 2: build multipart form (-F ...) including ALL fields + file
$formParts = @()
# Iterate PSCustomObject properties (NOT GetEnumerator)
$presign.fields.PSObject.Properties | ForEach-Object {
  $name  = $_.Name
  $value = $_.Value
  $formParts += @("-F", "$name=$value")
}
$formParts += @("-F", "file=@$File")

Info "Uploading to storage (curl -> $UploadUrl)..."
$upload = & curl.exe -sS -D - -o NUL -X POST $formParts $UploadUrl
$lastExit = $LASTEXITCODE
if ($lastExit -ne 0) {
  Fail "curl upload failed (exit $lastExit). Output:`n$upload"
  exit 1
}
if ($upload -match "HTTP/\d\.\d\s+(?<code>\d+)\s") {
  $code = [int]$Matches['code']
  if ($code -ge 200 -and $code -lt 300) {
    Ok "Upload success (HTTP $code)"
  } else {
    Fail "Upload returned HTTP $code. Headers:`n$upload"
    Warn "Likely cause: missing/altered presign fields, file > MAX_UPLOAD_MB, or bucket 'docs' not created."
    exit 1
  }
} else {
  Warn "Could not parse HTTP code from curl output. Raw:`n$upload"
}

# Step 3: notify API
$payload = @{
  key      = $presign.key
  filename = $leaf
  size     = $size
} | ConvertTo-Json

Info "Notifying API..."
try { $doc = Invoke-RestMethod -Method Post -Uri "$API/docs/notify" -ContentType "application/json" -Body $payload }
catch { Fail "Notify failed. $_"; exit 1 }

$docId = $doc.id
Ok "Notify ok → docId = $docId, status = $($doc.status)"

# Step 4: verify
Info "Listing docs..."
$docsList = Invoke-RestMethod "$API/docs"
$docsList | ForEach-Object { "{0,3}  {1}  {2}" -f $_.id, $_.status, $_.filename } | Write-Host

Info "Fetching detail for docId=$docId..."
$detail = Invoke-RestMethod "$API/docs/$docId"
Ok "Excerpt:"
$detail.excerpt | Write-Host

# Optional: quick chat
$chatBody = @{
  docId = $docId
  messages = @(
    @{ role="user"; content="Give me a one-line summary." }
  )
} | ConvertTo-Json -Depth 6
Info "Chat (dev mock)..."
$chatResp = Invoke-RestMethod -Method Post -Uri "$API/chat" -ContentType "application/json" -Body $chatBody
Ok "Chat reply:"
$chatResp.reply | Write-Host
