#!/bin/bash
# Validation script for HTTP stub services
# This script validates that the gateway stub services work correctly with the DocAssis backend

set -e

API_URL="http://localhost:8000"
OCR_URL="http://localhost:8081"
LLM_URL="http://localhost:8082"
REQUEST_ID="validate-$(date +%s)"

echo "=== Validating HTTP Stub Services ==="
echo ""

# Step 1: Check service health
echo "Step 1: Checking service health..."
if ! curl -sf "$OCR_URL/health" > /dev/null; then
    echo "ERROR: OCR service is not healthy at $OCR_URL"
    exit 1
fi
echo "✓ OCR service is healthy"

if ! curl -sf "$LLM_URL/health" > /dev/null; then
    echo "ERROR: LLM service is not healthy at $LLM_URL"
    exit 1
fi
echo "✓ LLM service is healthy"

if ! curl -sf "$API_URL/api/v1/health" > /dev/null; then
    echo "ERROR: API service is not healthy at $API_URL"
    exit 1
fi
echo "✓ API service is healthy"
echo ""

# Step 2: Create test file
echo "Step 2: Creating test file..."
TEST_CONTENT="This is a test document for OCR and LLM processing. It contains some sample text to verify that the gateway stub services work correctly."
echo "$TEST_CONTENT" > /tmp/test_doc.txt
echo "✓ Test file created: /tmp/test_doc.txt"
echo ""

# Step 3: Get presigned upload URL
echo "Step 3: Getting presigned upload URL..."
PRESIGN_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/docs/upload/presign" \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: $REQUEST_ID" \
  -d "{
    \"filename\": \"test.txt\",
    \"mime_type\": \"text/plain\",
    \"size_bytes\": $(stat -f%z /tmp/test_doc.txt 2>/dev/null || stat -c%s /tmp/test_doc.txt),
    \"domain\": \"IDENTITY\",
    \"doc_type\": \"PASSPORT\"
  }")

STORAGE_KEY=$(echo "$PRESIGN_RESPONSE" | grep -o '"storage_key":"[^"]*"' | cut -d'"' -f4)
UPLOAD_URL=$(echo "$PRESIGN_RESPONSE" | grep -o '"upload_url":"[^"]*"' | cut -d'"' -f4)

if [ -z "$STORAGE_KEY" ] || [ -z "$UPLOAD_URL" ]; then
    echo "ERROR: Failed to get presigned URL"
    echo "Response: $PRESIGN_RESPONSE"
    exit 1
fi
echo "✓ Presigned URL obtained"
echo "  Storage key: $STORAGE_KEY"
echo ""

# Step 4: Upload file
echo "Step 4: Uploading file to MinIO..."
UPLOAD_FIELDS=$(echo "$PRESIGN_RESPONSE" | grep -o '"upload_fields":{[^}]*}' || echo '{}')
if echo "$UPLOAD_FIELDS" | grep -q '{}'; then
    # Simple POST upload
    curl -sf -X POST "$UPLOAD_URL" -F "file=@/tmp/test_doc.txt" > /dev/null
else
    # Multipart form upload (if upload_fields present)
    curl -sf -X POST "$UPLOAD_URL" -F "file=@/tmp/test_doc.txt" > /dev/null
fi
echo "✓ File uploaded"
echo ""

# Step 5: Notify backend
echo "Step 5: Notifying backend of upload..."
NOTIFY_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/docs/notify" \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: $REQUEST_ID" \
  -d "{
    \"storage_key\": \"$STORAGE_KEY\",
    \"filename\": \"test.txt\",
    \"mime_type\": \"text/plain\",
    \"size_bytes\": $(stat -f%z /tmp/test_doc.txt 2>/dev/null || stat -c%s /tmp/test_doc.txt),
    \"domain\": \"IDENTITY\",
    \"doc_type\": \"PASSPORT\"
  }")

DOC_ID=$(echo "$NOTIFY_RESPONSE" | grep -o '"id":[0-9]*' | cut -d':' -f2)

if [ -z "$DOC_ID" ]; then
    echo "ERROR: Failed to notify backend"
    echo "Response: $NOTIFY_RESPONSE"
    exit 1
fi
echo "✓ Backend notified"
echo "  Document ID: $DOC_ID"
echo ""

# Step 6: Poll until ready
echo "Step 6: Polling document status..."
MAX_ATTEMPTS=30
ATTEMPT=0
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    DOC_RESPONSE=$(curl -s "$API_URL/api/v1/docs/$DOC_ID")
    STATUS=$(echo "$DOC_RESPONSE" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    OCR_STATUS=$(echo "$DOC_RESPONSE" | grep -o '"ocr_status":"[^"]*"' | cut -d'"' -f4)
    LLM_STATUS=$(echo "$DOC_RESPONSE" | grep -o '"llm_status":"[^"]*"' | cut -d'"' -f4)
    
    if [ "$STATUS" = "ready" ]; then
        echo "✓ Document processing completed"
        break
    fi
    
    if [ "$STATUS" = "error" ]; then
        echo "ERROR: Document processing failed"
        echo "Response: $DOC_RESPONSE"
        exit 1
    fi
    
    ATTEMPT=$((ATTEMPT + 1))
    echo "  Attempt $ATTEMPT/$MAX_ATTEMPTS: status=$STATUS, ocr_status=$OCR_STATUS, llm_status=$LLM_STATUS"
    sleep 2
done

if [ "$STATUS" != "ready" ]; then
    echo "ERROR: Document did not become ready within timeout"
    exit 1
fi
echo ""

# Step 7: Verify provider metadata
echo "Step 7: Verifying provider metadata..."
OCR_PROVIDER=$(echo "$DOC_RESPONSE" | grep -o '"provider":"[^"]*"' | head -1 | cut -d'"' -f4 || echo "")
LLM_PROVIDER=$(echo "$DOC_RESPONSE" | grep -o '"provider":"[^"]*"' | tail -1 | cut -d'"' -f4 || echo "")

echo "Key Fields:"
echo "  Status: $STATUS"
echo "  OCR Status: $OCR_STATUS"
echo "  LLM Status: $LLM_STATUS"
echo "  OCR Provider: $OCR_PROVIDER"
echo "  LLM Provider: $LLM_PROVIDER"
echo ""

# Verify providers
if [ "$OCR_PROVIDER" != "http" ]; then
    echo "WARNING: OCR provider is not 'http' (got: $OCR_PROVIDER)"
fi

if [ "$LLM_PROVIDER" != "http" ]; then
    echo "WARNING: LLM provider is not 'http' (got: $LLM_PROVIDER)"
fi

# Verify body content (for text files)
BODY=$(echo "$DOC_RESPONSE" | grep -o '"body":"[^"]*"' | cut -d'"' -f4 || echo "")
if [ -n "$BODY" ] && echo "$BODY" | grep -q "test document"; then
    echo "✓ Document body contains expected text (OCR read from MinIO)"
else
    echo "INFO: Document body: ${BODY:0:50}..."
fi

echo ""
echo "=== Validation Complete ==="
echo "Document ID: $DOC_ID"
echo "Request ID: $REQUEST_ID"
echo ""
echo "View full document: curl $API_URL/api/v1/docs/$DOC_ID"

