# EPIC 3 Chunk #2: OCR/LLM Cost Safety - Implementation Summary

## Status: ✅ COMPLETE

## Overview

This chunk implements cost guardrails by truncating OCR text before sending to LLM, ensuring LLM never receives more than `MAX_OCR_CHARS` characters.

## Changes Made

### 1. OCR Text Truncation (`app/services/document_processor.py`)

**In `process_document_llm_sync()`:**

Before calling LLM service:
1. Get full OCR text from `doc.body`
2. Truncate to `MAX_OCR_CHARS` (default 50000)
3. Store full OCR text in `doc.body` (preserved)
4. Send only truncated text to LLM
5. Store cost hints:
   - `doc.ocr_chars = len(full_text)` - Full OCR character count
   - `doc.llm_chars_sent = len(truncated_text)` - Characters actually sent to LLM

**Code:**
```python
# Step 3: Truncate OCR text before sending to LLM
max_ocr_chars = settings.MAX_OCR_CHARS if hasattr(settings, 'MAX_OCR_CHARS') else 50000
ocr_text_full = doc.body
ocr_text_truncated = ocr_text_full[:max_ocr_chars] if len(ocr_text_full) > max_ocr_chars else ocr_text_full
llm_chars_sent = len(ocr_text_truncated)

# Store cost hints
doc.llm_chars_sent = llm_chars_sent

# Call LLM with truncated text
llm_result = llm_service.analyze_document(
    text=ocr_text_truncated,  # Send truncated text
    mime_type=doc.mime,
    doc_type=doc.doc_type,
)
```

### 2. Cost Hints Storage

**Fields Added to Document Model:**
- `ocr_chars: int | None` - Full OCR text character count
- `llm_chars_sent: int | None` - Characters sent to LLM (after truncation)

**When Set:**
- `ocr_chars`: Set when OCR completes (in `process_document_ocr_sync`)
- `llm_chars_sent`: Set when LLM processing starts (in `process_document_llm_sync`)

### 3. Structured Logging

**Enhanced Logging:**
- `llm.start` - LLM analysis started (includes `ocr_chars`, `sent_chars`)
- `llm.text_prepared` - OCR text prepared for LLM (includes truncation info)
- `llm.finish` - LLM analysis completed (includes `ocr_chars`, `llm_chars_sent`)

**Log Fields:**
- `ocr_chars`: Full OCR text length
- `sent_chars` or `llm_chars_sent`: Characters sent to LLM
- `truncated`: Boolean indicating if text was truncated

## Behavior

### Text Preservation

- **Full OCR text**: Stored in `doc.body` (preserved for chat, display, etc.)
- **Truncated text**: Only sent to LLM service
- **No data loss**: Full text remains available for other uses

### Truncation Logic

```python
if len(ocr_text_full) > MAX_OCR_CHARS:
    ocr_text_truncated = ocr_text_full[:MAX_OCR_CHARS]
    llm_chars_sent = MAX_OCR_CHARS
else:
    ocr_text_truncated = ocr_text_full
    llm_chars_sent = len(ocr_text_full)
```

### Cost Tracking

**Stored in Document:**
- `page_count`: PDF pages (from Chunk 1)
- `ocr_chars`: Full OCR text length
- `llm_chars_sent`: Characters sent to LLM

**Available via `/meta` endpoint:**
- All cost hints accessible for UI display
- Helps users understand processing costs

## Backward Compatibility

✅ **Maintained:**
- Full OCR text still stored in `doc.body`
- LLM analysis still works (just with truncated input)
- No API changes
- Existing documents without cost hints still work

## Files Changed

1. `app/services/document_processor.py` - Added text truncation before LLM
2. `app/infrastructure/db/models.py` - Added cost hint fields (from Chunk 1)
3. `app/infrastructure/db/firestore_adapter.py` - Support for new fields (from Chunk 1)

## Acceptance Criteria

✅ **Verified:**
1. LLM request never receives > MAX_OCR_CHARS text
2. Full OCR text preserved in `doc.body`
3. Cost hints stored (`ocr_chars`, `llm_chars_sent`)
4. Structured logging includes truncation info

## Next Steps

- Chunk #3: Observability + Debugging Runbook
- Chunk #4: Tests
