# EPIC3: MVP Hardening + UX-ready API - Implementation Plan

## Overview
This epic focuses on hardening the API for production use with Flutter, adding essential features for multi-turn chat, streaming, quotas, and observability.

## Task Breakdown (PR-sized chunks)

### Chunk #1: Error Normalization + Tests ✅ (Current)
**Goal**: Ensure all endpoints return normalized error envelope `{error_code, message, details, request_id}`

**Files to touch**:
- `app/api/v1/docs.py` - Normalize all error responses
- `app/api/v1/health.py` - Check if errors exist
- `app/core/errors.py` - NEW: Shared error utilities module
- `tests/test_error_normalization.py` - NEW: Comprehensive error tests
- `tests/test_chat_errors.py` - NEW: Chat-specific error tests
- `tests/test_docs_errors.py` - NEW: Docs-specific error tests

**Implementation details**:
- Extract `normalize_error_response()` to shared module
- Update all HTTPException raises to use normalized format
- Add tests for all error scenarios (400, 404, 413, 422, 500, 502, 504)
- Ensure backward compatibility (existing clients still work)
- Edge cases: nested errors, upstream JSON errors, missing request_id

**Edge cases**:
- Upstream service returns JSON error → extract to details
- Missing request_id → generate one
- Nested error objects → flatten to message string
- Validation errors from Pydantic → map to VALIDATION_ERROR

---

### Chunk #2: Conversation History Persistence
**Goal**: Store chat conversations per doc_id, support multi-turn chat

**Files to touch**:
- `app/infrastructure/db/models.py` - Add ChatConversation model
- `app/infrastructure/db/sql_alchemy.py` - Migration (if needed)
- `app/infrastructure/db/db_helpers.py` - Add chat conversation helpers
- `app/api/v1/chat.py` - Load/save conversation history
- `app/schemas.py` - Update ChatRequestIn/ChatResponseOut if needed
- `tests/test_chat_history.py` - NEW: Conversation persistence tests

**Implementation details**:
- New model: `ChatConversation(doc_id, messages: JSON, updated_at)`
- Load conversation on chat request, merge with incoming messages
- Save conversation after successful LLM response
- Support both new messages array and legacy prompt/context
- Edge cases: doc_id doesn't exist, conversation too long, concurrent updates

**Database schema**:
```python
class ChatConversation(Base):
    __tablename__ = "chat_conversations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doc_id: Mapped[str] = mapped_column(String(64), index=True)
    messages: Mapped[List[dict]] = mapped_column(JSON)  # List of {role, content}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

---

### Chunk #3: SSE Streaming Endpoint
**Goal**: Add `/api/v1/chat/document/{doc_id}/stream` with Server-Sent Events

**Files to touch**:
- `app/api/v1/chat.py` - Add streaming endpoint
- `app/infrastructure/ai/base.py` - Add streaming support to LLM service (optional)
- `app/schemas.py` - Add streaming response schemas
- `tests/test_chat_streaming.py` - NEW: Streaming tests

**Implementation details**:
- Endpoint: `POST /api/v1/chat/document/{doc_id}/stream?stream=true`
- Query param `stream=true` enables streaming (backward compatible)
- Use FastAPI `StreamingResponse` with `text/event-stream`
- Format: `data: {"type": "chunk", "content": "..."}\n\n`
- Final: `data: {"type": "done", "reply": "full text"}\n\n`
- Fallback: If LLM service doesn't support streaming, return non-streaming response
- Edge cases: client disconnects, LLM timeout during stream, partial chunks

**Response format**:
```
data: {"type": "chunk", "content": "Hello"}

data: {"type": "chunk", "content": " world"}

data: {"type": "done", "reply": "Hello world", "model_used": "gemini-2.0-flash-lite-001"}

```

---

### Chunk #4: Quotas & Guardrails
**Goal**: Add input/output limits and basic rate limiting

**Files to touch**:
- `app/core/config.py` - Add quota configs
- `app/core/quotas.py` - NEW: Quota validation module
- `app/core/rate_limit.py` - NEW: Simple in-memory rate limiter
- `app/api/v1/chat.py` - Apply quotas and rate limits
- `app/api/v1/docs.py` - Apply OCR text length limits
- `tests/test_quotas.py` - NEW: Quota tests
- `tests/test_rate_limit.py` - NEW: Rate limit tests

**Implementation details**:
- Config: `MAX_INPUT_CHARS`, `MAX_MESSAGES`, `MAX_REPLY_CHARS`, `RATE_LIMIT_PER_IP`
- Rate limiter: Simple dict with IP → [timestamps], cleanup old entries
- Validate before LLM call: input chars, message count, reply length
- Return 413 for payload too large, 429 for rate limit
- Edge cases: IPv6 addresses, proxy headers (X-Forwarded-For), cleanup strategy

**Quota configs**:
```python
MAX_INPUT_CHARS: int = 100000  # From OCR text + context
MAX_MESSAGES: int = 50  # Per conversation
MAX_REPLY_CHARS: int = 50000  # Already exists
RATE_LIMIT_REQUESTS: int = 100  # Per IP
RATE_LIMIT_WINDOW_SEC: int = 60  # Per minute
```

---

### Chunk #5: Enhanced Observability
**Goal**: Structured logs with event names, latency tracking, trace context

**Files to touch**:
- `app/core/logging.py` - Add event name support, latency tracking
- `app/main.py` - Update RequestIdMiddleware to handle X-Cloud-Trace-Context
- `app/api/v1/chat.py` - Add event names to all logs
- `app/api/v1/docs.py` - Add event names to all logs
- `app/core/metrics.py` - NEW: Basic latency histogram (optional, simple dict)

**Implementation details**:
- Event names: `chat.request.started`, `chat.request.success`, `chat.request.fail`
- Latency: Track p50, p95, p99 (simple percentile calculation)
- X-Cloud-Trace-Context: Parse and forward to upstream services
- Structured logs: Always include event, request_id, duration_ms
- Edge cases: Missing trace context, invalid trace format, high cardinality events

**Log format**:
```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "event": "chat.request.success",
  "request_id": "req-123",
  "trace_id": "trace-456",
  "doc_id": "doc-789",
  "duration_ms": 1234.5,
  "latency_p95": 2000.0
}
```

---

### Chunk #6: LLM Gateway Improvements
**Goal**: /config endpoint, smarter retries, model_used in response

**Files to touch**:
- `services/gateway_stubs/gcp_llm_service/main.py` - Already has /config ✅
- `app/infrastructure/ai/base.py` - Update retry logic, handle model_used
- `app/api/v1/chat.py` - Extract model_used from LLM response
- `app/schemas.py` - Add model_used to ChatResponseOut (optional field)
- `tests/test_llm_gateway.py` - Update tests for model_used

**Implementation details**:
- Retry only on 404 (model not found) or 403 (permission denied)
- Don't retry on other 4xx (client errors)
- Extract model_used from LLM service response
- Include model_used in chat response (optional, backward compatible)
- Edge cases: LLM service doesn't return model_used, retry exhaustion

---

### Chunk #7: Documentation & Scripts
**Goal**: OpenAPI docs, README runbook, PowerShell scripts

**Files to touch**:
- `README.md` - Update with deployment, testing, debugging guide
- `docs/DEPLOYMENT.md` - NEW: Deployment guide
- `docs/DEBUGGING.md` - NEW: Debugging with request_id
- `scripts/upload.ps1` - NEW: Upload script
- `scripts/poll_status.ps1` - NEW: Poll document status
- `scripts/chat.ps1` - NEW: Chat script
- `scripts/fetch_logs.ps1` - NEW: Fetch logs by request_id
- `app/main.py` - Ensure OpenAPI schema is complete

**Implementation details**:
- PowerShell scripts use Invoke-RestMethod
- Log fetching: Use gcloud logging or Cloud Run logs API
- Include examples for all scripts
- Document request_id propagation end-to-end

---

## Implementation Order

1. ✅ **Chunk #1**: Error Normalization + Tests (STARTING NOW)
2. Chunk #2: Conversation History
3. Chunk #4: Quotas & Guardrails (before streaming)
4. Chunk #3: SSE Streaming
5. Chunk #5: Enhanced Observability
6. Chunk #6: LLM Gateway Improvements
7. Chunk #7: Documentation & Scripts

## Testing Strategy

Each chunk includes:
- Unit tests for core logic
- Integration tests for endpoints
- Error case tests
- Edge case tests
- Backward compatibility tests

## Backward Compatibility

- All existing endpoints remain unchanged
- New endpoints are additive only
- Optional fields in responses (model_used, etc.)
- Legacy request formats still supported
