"""Storage backend factory and wrapper implementations."""
from typing import Dict, Any
from app.core.config import get_settings
from app.infrastructure.storage.base import StorageBackend
from app.infrastructure.storage.s3_minio import presign_post, presign_get, get_bucket_name

settings = get_settings()


class S3MinIOStorageBackend:
    """S3/MinIO implementation of StorageBackend protocol."""
    
    def __init__(self):
        self.bucket = get_bucket_name()
        self.max_mb = settings.MAX_UPLOAD_MB
    
    def presign_upload(self, key: str, content_type: str) -> dict:
        """Generate a presigned URL for uploading a file.
        
        Args:
            key: The storage key/path for the file
            content_type: MIME type of the file
            
        Returns:
            Dictionary with 'url', 'fields', and 'key'
        """
        result = presign_post(self.bucket, key, self.max_mb)
        return {
            "url": result["url"],
            "fields": result.get("fields", {}),
            "key": key,
        }
    
    def presign_download(self, key: str, expires_in: int = 3600) -> str:
        """Generate a presigned URL for downloading a file.
        
        Args:
            key: The storage key/path for the file
            expires_in: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Presigned URL string
        """
        return presign_get(self.bucket, key, ttl=expires_in)


def get_storage_backend() -> StorageBackend:
    """Get the appropriate storage backend based on configuration.
    
    Returns:
        StorageBackend implementation
    """
    if settings.STORAGE_BACKEND == "s3_minio":
        return S3MinIOStorageBackend()
    # GCS, S3 AWS will be added later
    return S3MinIOStorageBackend()  # Default to MinIO for now

