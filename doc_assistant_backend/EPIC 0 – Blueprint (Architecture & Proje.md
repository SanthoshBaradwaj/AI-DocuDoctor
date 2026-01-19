EPIC 0 – Blueprint (Architecture & Project Re-alignment)

Goal:
Take the existing AI-DocuDoctor repo and reshape it into our new, scalable, AI-first, cloud-ready architecture without yet wiring all the AI logic. This epic is about foundation: structure, naming, modules, configs, and leaving clear extension points for all future features.

Scope (what EPIC 0 must achieve):

Align backend & frontend with our final product vision (identity, immigration, insurance, vehicles + finance & banking + employment & HR).

Remove or de-emphasize infra that doesn’t fit our target stack (e.g. MinIO, tight Celery/Redis coupling) while keeping the project runnable.

Introduce clean architecture boundaries:

API layer

Domain layer (document types, fields, rules)

Infrastructure layer (storage, DB, AI adapters, cloud providers)

Prepare for Google Cloud first, but cloud-agnostic later (can swap to AWS/other LLMs).

Keep Flutter app but trim / rename flows to match our new product.

Set up observability + config so we can scale to millions without changing structure later.

How to use this with Cursor

Don’t paste whole EPIC at once.

Take Chunk 1, paste into Cursor, let it refactor / modify code.

Then move to Chunk 2, and so on.

I’ll write each chunk so it’s “Cursor-ready”: clear, imperative, and scoped.

CHUNK 0 – Shared Vision & Target Architecture (no code changes)

This chunk is just to lock the mental model for both you and Cursor.

Objective:
Make sure the repo is being reshaped to this conceptual architecture:

Backend (Python / FastAPI):

Runs on Cloud Run (but must also run locally via uvicorn / Docker).

Uses Firestore OR Postgres as pluggable metadata storage:

EPIC 0: keep Postgres as primary for local dev, but design abstractions so Firestore can be added.

Uses Cloud Storage / S3-compatible interface for documents:

EPIC 0: keep MinIO as local dev backend, but abstract it so we can later plug in GCS/AWS S3.

Uses Pub/Sub-like abstraction for async jobs:

EPIC 0: Celery/Redis can stay as async mechanism, but behind a common “TaskQueue” interface so we can later plug in GCP Pub/Sub / AWS SQS.

Frontend (Flutter):

Mobile-first UX (Android/iOS), Web later.

Flows:

Auth (stub now, Firebase later)

Home dashboard (domains + alerts)

Upload docs

View docs

Per-doc chat

Global chat

Settings

AI Layer:

Abstractions for:

OCR provider (OcrService)

LLM provider (LLMService)

EPIC 0: just stubs, no Gemini calls yet.

Later: plug in Google Vision + Gemini, or swap to AWS Textract/Bedrock, or OpenAI, without breaking code.

Outcome of Chunk 0:
You and Cursor share this mental model, and everything that follows is consistent with it.

CHUNK 1 – Backend Reshape: Structure & Naming

Goal:
Modernize the backend structure to clearly separate API, domain, infrastructure, and prep for multi-cloud.

High-level tasks:

Keep the FastAPI app, but reorganize packages.

Current: app/main.py, db.py, models.py, services/…, routers/…

Target structure (example):

app/
  api/
    v1/
      docs.py
      chat.py
      health.py
  core/
    config.py
    logging.py
    security.py   # (even if stubbed)
  domain/
    documents/
      models.py       # Pydantic + domain models
      doc_types.py    # enums + config registry
      services.py     # business logic (no infra)
  infrastructure/
    db/
      sql_alchemy.py  # adapters to Postgres
    storage/
      s3_minio.py     # current MinIO
      base.py         # interfaces
    queue/
      celery_queue.py # current Celery
      base.py
    ai/
      base.py         # abstract LLM/OCR
  main.py


Don’t rip out Postgres/MinIO/Celery yet – instead:

Move them into infrastructure with clear interfaces.

This makes it very easy later to add:

Firestore implementation

GCS implementation

Pub/Sub task queue implementation

Different LLM integrations

Introduce versioned API path: /api/v1/...

Update routers from /docs, /chat to /api/v1/docs, /api/v1/chat.

What you’ll later tell Cursor (“EPIC0-CHUNK1 command style”):

“Refactor backend into app/api, app/domain, app/infrastructure as follows: …”

“Move current routers from app/routers/docs.py and chat.py into app/api/v1/docs.py and chat.py.”

“Move db.py, models.py into app/infrastructure/db/sql_alchemy.py and app/domain/documents/models.py.”

(You don’t have to send this to Cursor now; this blueprint tells you what that command will be.)

CHUNK 2 – Backend Config & Multi-Environment Setup

Goal:
Introduce a clean config system so we can easily run:

Local dev (docker-compose, Postgres, MinIO, Celery)

GCP dev/stage (Cloud Run, Firestore/GCS, Pub/Sub)

Future AWS migration (RDS, S3, SQS, Bedrock, etc.)

Key decisions:

Create app/core/config.py using Pydantic BaseSettings:

ENV (local, gcp, aws, etc.)

DATABASE_URL (for Postgres)

STORAGE_BACKEND (s3_minio, gcs, etc.)

QUEUE_BACKEND (celery, pubsub)

AI_BACKEND (gemini, openai, bedrock)

GOOGLE_PROJECT_ID, AWS_REGION, etc. (optional placeholders)

Convert hard-coded MinIO/S3/Redis configs to use config values.

Ensure docker-compose still works for local but doesn’t block cloud usage:

docker-compose becomes one environment (ENV=local).

Result:
We can spin up the same codebase in multiple environments by just changing env vars, not rewriting code.

CHUNK 3 – Document Domain Model & Doc Types Registry

Goal:
Re-align document data model with our final product domains and make it easy to add new doc types later.

3.1 Align Document Domain

From earlier: we’re supporting these domains in MVP 1:

Identity & Government IDs

Immigration & Travel

Insurance (Health/Auto)

Vehicles

Finance & Banking

Employment & HR

Within them, we start with a curated set of high-impact doc types (you already listed many; we’ll store them in config).

Tasks:

In app/domain/documents/doc_types.py define:

Domain enum: IDENTITY, IMMIGRATION, INSURANCE, VEHICLES, FINANCE, EMPLOYMENT_HR, …

DocType enum: PASSPORT, VISA, I94, I797, HEALTH_POLICY, AUTO_POLICY, INSURANCE_CARD, VEHICLE_REG, BANK_STATEMENT, PAYSTUB, EMPLOYMENT_CONTRACT, etc.

A registry: dictionary mapping doc_type → schema & rules.

For EPIC 0, schema can be minimal (just names), we’ll expand later.

In app/domain/documents/models.py:

Create Document domain model (Pydantic) with:

id, user_id, domain, doc_type, title, status, storage_key, expiry_date, etc.

Map DB model → domain model via adapter functions in infrastructure/db/sql_alchemy.py.

Keep the existing SQLAlchemy Document table but:

Add columns for domain and doc_type (string or enum).

Ensure it has extracted JSON field for AI-extracted data.

Outcome:
The backend now “thinks” in terms of our real product doc types, not just generic “documents”.

CHUNK 4 – API Contract Alignment (Docs & Chat)

Goal:
Define clear APIs matching our final app flows. No AI yet, just endpoints & shapes.

Docs APIs (/api/v1/docs):

GET /api/v1/docs

Query by domain, status, etc.

GET /api/v1/docs/{id}

Full details: metadata + extracted fields (if any).

POST /api/v1/docs/upload/presign (or similar)

Returns upload target for file (still MinIO locally).

Later can return GCS signed URL.

POST /api/v1/docs/notify

Called after file upload is complete.

Kicks off async extraction.

Later (not necessarily EPIC 0):

POST /api/v1/docs/{id}/reprocess

DELETE /api/v1/docs/{id} etc.

Chat APIs (/api/v1/chat):

POST /api/v1/chat/document/{doc_id}

request: messages, doc_id

response: assistant reply

POST /api/v1/chat/global

request: messages, optional filters (domains)

response: assistant reply using all docs as context

EPIC 0: these endpoints can return stubbed responses, but their shapes must be final. Cursor will later wire in AI logic.

CHUNK 5 – AI Service Abstractions (No Real AI Yet)

Goal:
Create interfaces for OCR & LLM so we can plug in Gemini, OpenAI, Bedrock, etc. later without touching API code.

In app/infrastructure/ai/base.py:

Define class OcrService(Protocol) with method:

extract_text(file_bytes: bytes, mime_type: str) -> OcrResult

Define class LLMService(Protocol) with methods:

classify_doc_type(text: str) -> DocType

extract_fields(doc_type: DocType, text: str) -> dict

chat(messages: list[Message], context: Optional[dict]) -> str

In app/infrastructure/ai/fake_stub.py:

Implement fake OcrService and LLMService that:

Just returns sample text / echo responses.

This lets you run the whole system without actual AI costs in early local testing.

Later:

Add gemini_service.py implementing LLMService.

Add vision_service.py implementing OcrService.

Or openai_service.py, bedrock_service.py, etc.

Outcome:
All AI calls are centralized & swappable.

CHUNK 6 – Queue Abstraction (Celery → Pub/Sub-ready)

Goal:
Keep Celery/Redis working now, but hide behind a TaskQueue interface so we can later:

Replace with GCP Pub/Sub + Cloud Run jobs.

Or AWS SQS + Lambda, etc.

In app/infrastructure/queue/base.py:

Define class TaskQueue(Protocol) with methods:

enqueue_ocr(document_id: str)

enqueue_extraction(document_id: str)

enqueue_reminder_scan()

etc.

In app/infrastructure/queue/celery_queue.py:

Implement TaskQueue using existing Celery tasks.

Later:

Add pubsub_queue.py for GCP.

API layer & domain layer only talk to TaskQueue, never directly to Celery/Pub/Sub.

CHUNK 7 – Observability & Error Handling Skeleton

Goal:
Set up logging + error structure so when we add AI & cloud later, debugging is sane.

Tasks:

app/core/logging.py:

Configure Python logging to use JSON-like structured logs.

Include request_id, user_id (if available), route, status_code.

Add FastAPI middleware:

Generate request_id header.

Log start/end of request.

Add a basic error handler:

Catch unhandled exceptions.

Return sanitized error messages to client.

Log internal details for server logs.

Add very simple internal health endpoints:

/api/v1/health

/api/v1/health/deps (checks DB connectivity etc.)

This is important for scalability + SRE practice later.

CHUNK 8 – Frontend (Flutter) Realignment

Goal:
Align Flutter app screens and services with our new backend contract and product direction.

Tasks:

Clean up routes:

Keep: login (even if mock), home, docs list, doc detail, upload, chat, settings.

Remove or de-emphasize: “webhooks”, “random analysis screens” that don’t match new flows.

Align /docs and /chat calls with /api/v1/... paths.

Introduce domain tabs/filters:

Identity, Immigration, Insurance, Vehicles, Finance, Employment/HR.

Chat screens:

One for document chat (doc-specific).

One for global chat.

Make sure UI reflects states:

Uploaded, Processing, Ready, Error.

EPIC 0: we can still use mock AI responses, but the UX should look like the final product.

CHUNK 9 – Checklist & Acceptance Criteria for EPIC 0

EPIC 0 is done when:

Backend

Has the new structure (api, domain, infrastructure, core).

Uses config/env to pick DB/storage/queue/AI.

Provides stable, versioned APIs: /api/v1/docs, /api/v1/chat.

Has stub AI services wired in via interfaces.

Has a TaskQueue abstraction for async jobs.

Has basic logging & error handling.

Frontend

Uses new API paths.

Has flows: login → home → docs → detail → chat.

Shows document domains & statuses.

Local dev

docker-compose up still works for local env.

You can:

upload a file,

see it in the list,

open details,

“chat” (even if AI is stubbed).

Scalability & extensibility

You can see exactly where to:

plug in Gemini & Vision,

switch to GCP managed services,

later add AWS / other LLMs,

add new document types via config.