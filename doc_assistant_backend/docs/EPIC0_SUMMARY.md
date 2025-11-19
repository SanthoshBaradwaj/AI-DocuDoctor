# EPIC 0 Summary: Backend Reshape and Frontend Alignment

## Overview

AI-DocuDoctor is a document management and AI-powered assistant application that helps users organize, extract, and chat about their important documents across multiple domains (Identity, Immigration, Insurance, Vehicles, Finance, Employment HR). The backend has been refactored into a clean layered architecture with cloud-agnostic abstractions, and the Flutter frontend has been aligned with the new API contracts. The system currently uses PostgreSQL, MinIO, and Celery for local development, with abstractions in place to easily swap in GCP (Cloud Run, GCS, Firestore, Pub/Sub, Gemini) or AWS (RDS, S3, SQS, Bedrock) services.

## Backend Architecture

The backend follows a clean layered architecture with clear separation of concerns:

### Layer Structure

- **`app/api/`** - FastAPI route handlers and request/response schemas
  - `v1/` - Versioned API endpoints (docs, chat, health)
  - All routes use `/api/v1/` prefix
  - Routes depend on infrastructure and domain layers, never directly on concrete implementations

- **`app/core/`** - Core application configuration and cross-cutting concerns
  - `config.py` - Centralized Settings class using Pydantic BaseSettings
  - `logging.py` - Structured JSON-like logging with request ID support
  - `security.py` - Placeholder for future auth/security logic

- **`app/domain/`** - Domain models and business logic
  - `documents/` - Document domain models, doc types registry, and business rules
  - Domain models are Pydantic models separate from DB ORM
  - No dependencies on infrastructure layer

- **`app/infrastructure/`** - External service integrations
  - `db/` - SQLAlchemy setup, ORM models, database session management
  - `storage/` - Storage backend abstraction (S3/MinIO implementation)
  - `queue/` - Task queue abstraction (Celery implementation)
  - `ai/` - LLM and OCR service abstractions (fake stub implementations)

### Current Local Implementations

- **Database**: PostgreSQL with pgvector extension (via SQLAlchemy ORM)
- **Storage**: MinIO (S3-compatible) via boto3
- **Queue**: Celery with Redis broker/backend
- **AI/OCR**: Fake stub implementations for local development

### Abstraction Benefits

All external services are behind clean interfaces:
- **StorageBackend** protocol allows swapping MinIO → GCS → S3 without changing API code
- **TaskQueue** protocol allows swapping Celery → Pub/Sub → SQS without changing API code
- **LLMService** and **OcrService** protocols allow swapping fake → Gemini → OpenAI → Bedrock via configuration
- Centralized `Settings` class enables environment-based configuration switching

## Domain and Document Model

### Document Domains

The system supports six main document domains:

1. **IDENTITY** - Government IDs and identity documents
2. **IMMIGRATION** - Travel and immigration documents
3. **INSURANCE** - Health and auto insurance policies
4. **VEHICLES** - Vehicle registration and related documents
5. **FINANCE** - Banking and financial documents
6. **EMPLOYMENT_HR** - Employment and HR-related documents

### Document Types

Currently configured document types include:

**Identity & Government IDs:**
- PASSPORT
- NATIONAL_ID
- DRIVERS_LICENSE

**Immigration & Travel:**
- VISA
- I94_OR_ENTRY_RECORD
- I797_OR_STATUS_NOTICE

**Insurance:**
- HEALTH_INSURANCE_POLICY
- AUTO_INSURANCE_POLICY
- INSURANCE_ID_CARD

**Vehicles:**
- VEHICLE_REGISTRATION

**Finance & Banking:**
- BANK_STATEMENT
- CREDIT_CARD_STATEMENT
- LOAN_OR_MORTGAGE_AGREEMENT

**Employment & HR:**
- PAYSLIP_OR_PAYSTUB
- EMPLOYMENT_CONTRACT
- BENEFITS_SUMMARY

### Document Type Registry

The `DOC_TYPE_REGISTRY` in `app/domain/documents/doc_types.py` defines:
- **FieldConfig** - Field definitions (name, label, type, required, drives_expiry)
- **DocTypeConfig** - Complete document type configuration (domain, display_name, description, fields)
- Helper functions to query the registry by document type or domain

This registry-based approach allows adding new document types, countries, or languages via configuration without rewriting backend code.

### Domain Model

- **Domain Document Model** (`app/domain/documents/models.py`): Pydantic models separate from DB ORM
  - Includes `domain`, `doc_type`, `expiry_date`, `extracted` fields
  - Mapping functions to convert between DB models and domain models

- **DB Model** (`app/infrastructure/db/models.py`): SQLAlchemy ORM models
  - Includes `domain`, `doc_type`, `expiry_date` columns (indexed)
  - `extracted` JSON column for AI-extracted structured data

## API Surface

All endpoints are versioned under `/api/v1/`:

### Documents API (`/api/v1/docs`)

- **`GET /api/v1/docs`** - List documents with optional filtering by `domain`, `doc_type`, `status`
- **`GET /api/v1/docs/{doc_id}`** - Get full document details including domain, doc_type, expiry_date, extracted fields
- **`POST /api/v1/docs/upload/presign`** - Initialize upload, get presigned URL (uses StorageBackend abstraction)
- **`POST /api/v1/docs/notify`** - Notify upload completion, create DB record, enqueue OCR task (uses TaskQueue abstraction)
- **`POST /api/v1/docs/analyze`** - Legacy/transitional endpoint for document analysis

### Chat API (`/api/v1/chat`)

- **`POST /api/v1/chat/document/{doc_id}`** - Document-specific chat (uses LLMService abstraction)
- **`POST /api/v1/chat/global`** - Global chat across all documents (uses LLMService abstraction)

### Health API (`/api/v1/health`)

- **`GET /api/v1/health`** - Basic application status
- **`GET /api/v1/health/deps`** - Dependency health checks (database, storage, queue)

All endpoints use the abstractions (StorageBackend, TaskQueue, LLMService) rather than direct service calls, making them cloud-agnostic.

## Infrastructure Abstractions

### Storage Abstraction

- **Protocol**: `StorageBackend` in `app/infrastructure/storage/base.py`
  - Methods: `presign_upload()`, `presign_download()`
- **Current Implementation**: `S3MinIOStorageBackend` in `app/infrastructure/storage/s3_minio.py`
- **Factory**: `get_storage_backend()` in `app/infrastructure/storage/storage_factory.py`
  - Selects implementation based on `STORAGE_BACKEND` setting (s3_minio, gcs, s3_aws)

### Task Queue Abstraction

- **Protocol**: `TaskQueue` in `app/infrastructure/queue/base.py`
  - Methods: `enqueue_ocr(document_id)`
- **Current Implementation**: `CeleryTaskQueue` in `app/infrastructure/queue/celery_queue.py`
  - Wraps Celery `process_document_ocr` task
- **Factory**: `get_task_queue()` in `app/infrastructure/queue/celery_queue.py`
  - Selects implementation based on `QUEUE_BACKEND` setting (celery, future: pubsub, sqs)

### AI Service Abstractions

- **Protocols**: `LLMService` and `OcrService` in `app/infrastructure/ai/base.py`
- **Current Implementation**: `FakeLLMService` and `FakeOcrService` (stubs for local dev)
- **Factories**: `get_llm_service()` and `get_ocr_service()`
  - Select implementation based on `AI_BACKEND` setting (fake, future: gemini, openai, bedrock)

### Centralized Configuration

- **Settings Class**: `app/core/config.py` using Pydantic `BaseSettings`
- All configuration via environment variables or `.env` file
- Key settings: `APP_ENV`, `STORAGE_BACKEND`, `QUEUE_BACKEND`, `AI_BACKEND`, database URLs, etc.
- Enables switching between local, GCP, and AWS without code changes

## Observability and Health

### Logging

- **Structured Logging**: JSON-like format with timestamp, level, logger name, message, request_id
- **Request ID Propagation**: Using `contextvars` to propagate request_id through async contexts
- **Configuration**: Log level controlled via `LOG_LEVEL` setting
- **Celery Integration**: Worker uses same logging configuration

### Request ID Middleware

- **RequestIdMiddleware**: Generates UUID4 request IDs if not provided in `X-Request-ID` header
- Attaches to `request.state.request_id` and response header `X-Request-ID`
- All logs include request_id for tracing requests across services

### Error Handling

- **Global Exception Handlers**: Consistent JSON error responses
  - `HTTPException` handler with error codes (VALIDATION_ERROR, NOT_FOUND, etc.)
  - Generic `Exception` handler for unhandled errors
- **Error Response Format**: `{error_code, message, request_id}`
- **Internal Logging**: Detailed error logs with stack traces (not exposed to clients)

### Health Checks

- **Basic Health**: `GET /api/v1/health` returns app status, app_env, app_name
- **Dependency Health**: `GET /api/v1/health/deps` checks:
  - Database: `SELECT 1` query
  - Storage: Lightweight bucket check (head_bucket for S3/MinIO)
  - Queue: Redis ping for Celery
- **Status Levels**: `ok`, `degraded`, `error`

## Frontend Status

### Flutter App Structure

The Flutter app (`doc_assistant/`) has been aligned with the new backend API contracts:

### Routes

- **Auth**: `/login`, `/signup`, `/forgot`
- **Home**: `/home` with navigation to:
  - Documents (`/home/docs`)
  - Upload (`/home/upload`)
  - Chat (`/home/chat` with optional `?docId=123` for document-scoped chat)
  - Settings (`/home/settings`)

### Document Management

- **Documents List** (`lib/features/docs/docs_page.dart`):
  - Displays domain, doc type, status, expiry date
  - Domain filter chips (All, Identity, Immigration, Insurance, Vehicles, Finance, Employment HR)
  - Calls `GET /api/v1/docs` with optional domain filter

- **Document Detail** (`lib/features/docs/doc_detail_page.dart`):
  - Shows all metadata: domain, doc type, expiry date, extracted fields
  - "Chat About Document" button navigates to chat with docId

- **Upload** (`lib/features/upload/upload_page.dart`):
  - Uses new 3-step flow: `initUpload()` → `uploadToPresigned()` → `notifyUploaded()`
  - Calls `POST /api/v1/docs/upload/presign` and `POST /api/v1/docs/notify`

### Chat

- **Chat Page** (`lib/features/chat/chat_page.dart`):
  - Supports two modes: document-scoped (with docId) and global (without docId)
  - Document chat: Calls `POST /api/v1/chat/document/{doc_id}`
  - Global chat: Calls `POST /api/v1/chat/global`
  - Handles new `ChatResponseOut` format with `messages` array

### API Client

- **Base URL**: `http://{host}:8000/api/v1` (includes version prefix)
- **All endpoints** use versioned paths
- **Models** (`lib/models/doc.dart`) include `domain`, `docType`, `expiryDate` fields

## Key Architectural Decisions

1. **Layered Architecture**: Clear separation between API, domain, infrastructure, and core layers prevents circular dependencies and enables easy testing and swapping of implementations.

2. **Abstraction Over Implementation**: All external services (storage, queue, AI) are behind protocols/interfaces, allowing cloud-agnostic deployment.

3. **Domain-Driven Design**: Domain models separate from infrastructure models enable business logic to evolve independently of persistence concerns.

4. **Configuration-Driven**: Centralized Settings class enables environment-based switching without code changes.

5. **Versioned API**: All endpoints under `/api/v1/` prefix for future API evolution.

6. **Structured Observability**: Request ID tracing and structured logging enable debugging and monitoring in distributed environments.

## Next Steps (Post-EPIC 0)

- Implement real AI services (Gemini, OpenAI, Bedrock) behind LLMService/OcrService protocols
- Add real OCR processing (Gemini Vision, Tesseract, etc.)
- Implement GCP and AWS storage/queue backends
- Add authentication and authorization
- Implement document expiry reminders based on `expiry_date` and `drives_expiry` fields
- Enhance document extraction to populate structured fields from `DOC_TYPE_REGISTRY`
- Add vector embeddings and semantic search using pgvector
- Polish Flutter UI/UX

