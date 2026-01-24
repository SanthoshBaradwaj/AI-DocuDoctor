# AI-DocuDoctor

AI-powered document management and assistant application with FastAPI backend and Flutter frontend.

## Project Structure

```
AI-DocuDoctor/
├── doc_assistant_backend/    # FastAPI backend
│   ├── app/
│   │   ├── api/v1/          # Versioned API endpoints
│   │   ├── core/            # Configuration and logging
│   │   ├── domain/          # Domain models and business logic
│   │   └── infrastructure/ # External service integrations
│   └── docker-compose.yml    # Local development setup
└── doc_assistant/            # Flutter frontend
    └── lib/                  # Flutter application code
```

## Quick Start

### Backend Setup

1. Navigate to backend directory:
```bash
cd doc_assistant_backend
```

2. Start services with Docker Compose:
```bash
docker compose up -d
```

This starts:
- PostgreSQL (port 5432)
- MinIO S3 storage (port 9000)
- Redis (port 6379)
- FastAPI backend (port 8000)
- Celery worker

3. Verify backend is running:
```bash
curl http://localhost:8000/api/v1/health
```

### Frontend Setup

1. Navigate to Flutter app directory:
```bash
cd doc_assistant
```

2. Install dependencies:
```bash
flutter pub get
```

3. Run in Chrome:
```bash
flutter run -d chrome
```

The app will connect to `http://localhost:8000/api/v1` automatically when running in Chrome.

## Backend API

All endpoints are versioned under `/api/v1/`:

- **Documents**: `GET /api/v1/docs`, `GET /api/v1/docs/{id}`, `POST /api/v1/docs/upload/presign`, `POST /api/v1/docs/notify`
- **Chat**: `POST /api/v1/chat/document/{doc_id}`, `POST /api/v1/chat/global`
- **Health**: `GET /api/v1/health`, `GET /api/v1/health/deps`

### Debugging

- **How to debug with request_id**: See `doc_assistant_backend/docs/DEBUGGING_RUNBOOK.md`
- **Status interpretation**: See `doc_assistant_backend/docs/DEBUGGING_RUNBOOK.md#status-interpretation-guide`
- **PowerShell scripts**: See `doc_assistant_backend/scripts/` for upload, poll_status, chat, and fetch_logs

See `doc_assistant_backend/docs/EPIC0_SUMMARY.md` for detailed architecture documentation.

## Frontend Features

- **Documents List**: View all documents with domain filtering
- **Document Detail**: View full document metadata and extracted fields
- **Upload**: 3-step upload pipeline with domain/document type selection
- **Chat**: Document-scoped and global chat modes
- **Navigation**: Clean home navigation (Documents, Upload, Chat, Settings)

## Development

### Backend

- Environment variables configured in `docker-compose.yml`
- Logging with structured JSON format and request ID tracing
- Health checks for all dependencies
- All external services abstracted (StorageBackend, TaskQueue, LLMService)

### Frontend

- API base URL auto-detects web vs mobile
- All API calls use versioned `/api/v1/` endpoints
- Models aligned with backend Pydantic schemas
- Domain and document type filtering
- Upload with progress tracking

## Architecture

### Backend Layers

- **API** (`app/api/v1/`): FastAPI route handlers
- **Core** (`app/core/`): Configuration, logging, security
- **Domain** (`app/domain/`): Business models and rules
- **Infrastructure** (`app/infrastructure/`): DB, storage, queue, AI services

### Document Domains

- Identity & Government IDs
- Immigration & Travel
- Insurance (Health/Auto)
- Vehicles & Transportation
- Finance & Banking
- Employment & HR

## Next Steps

- Implement real AI services (Gemini, OpenAI, Bedrock)
- Add real OCR processing
- Implement GCP and AWS backends
- Add authentication and authorization
- Enhance document extraction
- Add vector embeddings and semantic search

See `doc_assistant_backend/docs/EPIC0_SUMMARY.md` for complete architecture details.

