import 'package:flutter/foundation.dart';

/// FastAPI base URL for web (Chrome)
const String kWebApiBase = 'http://localhost:8000/api/v1';

/// FastAPI base URL for Android emulator or device
/// Use your PC's LAN IP so your phone can reach Docker services.
/// Example: 192.168.0.42 (no http:// here)
const String kDefaultApiBase = 'http://10.0.0.79:8000/api/v1';

/// Single source of truth for backend API base URL
String get kApiBase => kIsWeb ? kWebApiBase : kDefaultApiBase;

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
