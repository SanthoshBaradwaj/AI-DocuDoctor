"""GCS StorageBackend implementation."""
from typing import Dict, Any
from app.core.config import get_settings
from app.infrastructure.storage.base import StorageBackend
from app.infrastructure.storage.gcs_storage import (
    get_gcs_bucket_name,
    presign_upload_v4,
    presign_download_v4,
    format_storage_key,
)

settings = get_settings()


class GCSStorageBackend:
    """Google Cloud Storage implementation of StorageBackend protocol."""
    
    def __init__(self):
        self.bucket = get_gcs_bucket_name()
        self.max_mb = settings.MAX_UPLOAD_MB
    
    def presign_upload(self, key: str, content_type: str) -> Dict[str, Any]:
        """Generate a presigned URL for uploading a file to GCS.
        
        Args:
            key: The storage key/path for the file (can be object path or gs:// URL)
            content_type: MIME type of the file
            
        Returns:
            Dictionary with 'url', 'fields' (empty for GCS V4), and 'key'
        """
        # Extract object path from gs:// URL if needed
        object_path = key
        if key.startswith("gs://"):
            # Parse gs://bucket/path -> path
            parts = key.replace("gs://", "").split("/", 1)
            if len(parts) > 1:
                object_path = parts[1]
            else:
                object_path = parts[0]
        
        result = presign_upload_v4(self.bucket, object_path, content_type)
        
        # Return key in gs:// format for consistency
        formatted_key = format_storage_key(object_path, self.bucket)
        
        return {
            "url": result["url"],
            "fields": result["fields"],
            "key": formatted_key,  # Return gs:// URL format
        }
    
    def presign_download(self, key: str, expires_in: int = 3600) -> str:
        """Generate a presigned URL for downloading a file from GCS.
        
        Args:
            key: The storage key/path for the file (can be object path or gs:// URL)
            expires_in: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Presigned URL string
        """
        # Extract object path from gs:// URL if needed
        object_path = key
        if key.startswith("gs://"):
            # Parse gs://bucket/path -> path
            parts = key.replace("gs://", "").split("/", 1)
            if len(parts) > 1:
                object_path = parts[1]
            else:
                object_path = parts[0]
        
        return presign_download_v4(self.bucket, object_path, expires_in)
