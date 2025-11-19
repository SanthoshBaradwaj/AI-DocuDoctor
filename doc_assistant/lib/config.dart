/// Set these to your PC's LAN IP so your phone can reach Docker services.
/// Example: 192.168.0.42 (no http:// here)
const kDevHost = '10.0.0.79';

/// FastAPI (compose exposes 8000 on host)
/// Base URL includes /api/v1 prefix
const kApiBase = 'http://$kDevHost:8000/api/v1';

/// MinIO S3 (compose exposes 9000 on host)
const kStorageBase = 'http://$kDevHost:9000';

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

const kUseUploadProxy = true;
