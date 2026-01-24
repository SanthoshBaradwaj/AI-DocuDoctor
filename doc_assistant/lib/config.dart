import 'package:flutter/foundation.dart';

/// FastAPI base URL for web (Chrome) - local development
/// NOTE: Do NOT include /api/v1 here - routes add it
const String kWebApiBase = 'http://localhost:8000';

/// FastAPI base URL for Android emulator or device - local development
/// Use your PC's LAN IP so your phone can reach Docker services.
/// NOTE: Do NOT include /api/v1 here - routes add it
const String kDefaultApiBase = 'http://10.0.0.79:8000';

/// Cloud Run production URL (set via environment or build config)
/// Example: 'https://docassis-api-xxxxx.run.app'
/// NOTE: Do NOT include /api/v1 here - routes add it
const String kCloudRunApiBase = String.fromEnvironment(
  'CLOUD_RUN_API_BASE',
  defaultValue: '',
);

/// Single source of truth for backend API base URL
/// Priority: Cloud Run URL (if set) > Web (if web) > Default (mobile)
/// NOTE: baseUrl should NOT include /api/v1 - that's added by routes
String get kApiBase {
  if (kCloudRunApiBase.isNotEmpty) {
    // Remove /api/v1 if present (routes will add it)
    final url = kCloudRunApiBase.trim();
    if (url.endsWith('/api/v1')) {
      return url.substring(0, url.length - 7);
    }
    if (url.endsWith('/api/v1/')) {
      return url.substring(0, url.length - 8);
    }
    return url;
  }
  return kIsWeb ? kWebApiBase : kDefaultApiBase;
}

/// Test mode: Use hardcoded document ID for debugging
const bool kTestMode = bool.fromEnvironment('TEST_MODE', defaultValue: false);
const String kTestDocId = '1'; // Hardcoded doc ID for test mode (string)

/// MinIO S3 (compose exposes 9000 on host)
const kStorageBase = 'http://10.0.0.79:9000';

/// Allowed file extensions in picker
const kAllowedExtensions = [
  'txt',
  'pdf',
  'doc',
  'docx',
  'xlsx',
  'jpg',
  'jpeg',
  'png'
];

/// Max dev file size hint (MB). Server enforces its own limit too.
const kMaxDevFileMb = 50;
