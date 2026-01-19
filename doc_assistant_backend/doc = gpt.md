Epic 0: Align architecture & remove outdated infra

Epic 1: Wire backend to Google Cloud (Firestore, Storage, etc.)

Epic 2: Plug in OCR + Gemini extraction

Epic 3: Plug in AI chat (doc + global)

Epic 4: Add reminders + knowledge cards

Epic 5: Frontend polish + UX 


EPIC1-CHUNK2 – “Real OCR implementation”

Goal:
Implement a real OcrService that actually reads from storage and extracts text.

Suggested approach (Cursor will implement details):

Add OcrResult model (text, page_count, language, confidence, etc.)

Implement TesseractOcrService or “LocalOcrService” that:

Downloads bytes from storage (via a new read_bytes() on StorageBackend)

Handles PDFs vs images

Updates body, excerpt, extracted (basic fields like full_text, maybe pages)

Keep it behind a config like OCR_BACKEND=fake|local.

EPIC1-CHUNK3 – “Real LLMService for doc chat + global chat”

Goal:
Wire a real LLM provider while keeping abstractions intact.

Extend LLMService with a clean chat(messages, context) interface

Add implementation (e.g. OpenAILLMService or GeminiLLMService) using env vars

Document chat: include document excerpt/body as context

Global chat: summarize domain counts and optionally sample excerpts

Keep fake backend as default; enable real one via AI_BACKEND=openai (or similar)

EPIC1-CHUNK4 – “Statuses, UX, and error surfacing”

Goal:
Make the system feel like a real product around the new pipeline.

Clear status state machine: uploaded → processing → ready | error

DB + domain model + API + Flutter align on these statuses

Store error_message on documents when OCR/LLM fails

Flutter:

Show spinners while processing

Disable chat until ready

Show friendly error state if error

EPIC1-CHUNK5 – “Config, health and docs for AI/OCR”

Goal:
Harden for local and later cloud use.

Settings for:

AI_BACKEND, AI_MODEL, AI_API_KEY

OCR_BACKEND

/api/v1/health/deps extended with AI/OCR checks

docs/EPIC1_SUMMARY.md with how to run OCR/LLM locally and what env vars to set

README updated with quick “turn real AI on” instructions