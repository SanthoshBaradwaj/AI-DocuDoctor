# AI-DocuDoctor Flutter Frontend

This is the Flutter frontend application for AI-DocuDoctor, aligned with the EPIC 0 backend contracts.

## Prerequisites

- Flutter SDK (latest stable version)
- Dart SDK
- Chrome browser (for web development)
- Backend running on `http://localhost:8000` (see backend README)

## Setup

1. Install dependencies:
```bash
flutter pub get
```

2. Ensure the backend is running:
```bash
cd ../doc_assistant_backend
docker compose up -d
```

## Running the App

### Web (Chrome)

```bash
flutter run -d chrome
```

The app will automatically connect to `http://localhost:8000/api/v1` when running in Chrome.

### Android Emulator/Device

For Android, update `kDefaultApiBase` in `lib/config.dart` to use your PC's LAN IP address so the device can reach the Docker services.

```bash
flutter run -d <device-id>
```

## Main Features

### Documents
- List all documents with domain and document type
- Filter by domain (Identity, Immigration, Insurance, Vehicles, Finance, Employment HR)
- View document details including extracted fields and expiry date
- Navigate to document-specific chat

### Upload
- Select domain and document type
- Upload files using the 3-step pipeline:
  1. Initialize upload (get presigned URL)
  2. Upload file to storage
  3. Notify backend
- Progress tracking for each step

### Chat
- **Document-scoped chat**: Chat about a specific document
- **Global chat**: Chat across all documents
- Real-time message display with mock AI responses

### Navigation
- Home dashboard
- Documents list
- Upload page
- Chat (document or global)
- Settings

## API Endpoints

All API calls use versioned endpoints under `/api/v1/`:

- `GET /api/v1/docs` - List documents (with optional filters)
- `GET /api/v1/docs/{id}` - Get document details
- `POST /api/v1/docs/upload/presign` - Initialize upload
- `POST /api/v1/docs/notify` - Notify upload completion
- `POST /api/v1/chat/document/{doc_id}` - Document chat
- `POST /api/v1/chat/global` - Global chat
- `GET /api/v1/health` - Health check

## Project Structure

```
lib/
├── config.dart              # API base URL configuration
├── models/
│   ├── doc.dart            # Document models (Doc, DocDetail)
│   └── chat.dart           # Chat models (ChatMessage, ChatResponse)
├── services/
│   └── api_client.dart     # API client with all endpoint methods
├── features/
│   ├── docs/               # Documents list and detail pages
│   ├── upload/             # Upload page with 3-step pipeline
│   ├── chat/               # Chat page and controllers
│   ├── home/               # Home navigation
│   └── auth/               # Authentication (mock)
└── routing/
    └── app_router.dart     # GoRouter configuration
```

## Configuration

The API base URL is configured in `lib/config.dart`:

- **Web**: `http://localhost:8000/api/v1`
- **Mobile**: `http://10.0.0.79:8000/api/v1` (update with your LAN IP)

## Troubleshooting

### Backend Connection Issues

1. Ensure backend is running: `docker compose ps` in `doc_assistant_backend`
2. Check backend health: `curl http://localhost:8000/api/v1/health`
3. Verify CORS settings in backend allow requests from Flutter web

### Upload Issues

- For web, ensure MinIO is accessible at `http://localhost:9000`
- Check file size limits (default: 25MB)
- Verify domain and document type are selected before upload

### Chat Issues

- Ensure backend chat endpoints are responding
- Check browser console for CORS or network errors
- Verify request payload matches backend schema

## Development Notes

- All API calls use the new `/api/v1/` versioned endpoints
- Models align with backend Pydantic schemas
- Upload uses 3-step pipeline: presign → upload → notify
- Chat supports both document-scoped and global modes
- Domain filtering uses backend enum values (IDENTITY, IMMIGRATION, etc.)
