from typing import Protocol

class StorageBackend(Protocol):
    """Protocol defining the interface for storage backends."""
    
    def presign_upload(self, key: str, content_type: str) -> dict:
        """Generate a presigned URL for uploading a file.
        
        Args:
            key: The storage key/path for the file
            content_type: MIME type of the file
            
        Returns:
            Dictionary with 'url', 'fields', and 'key'
        """
        ...
    
    def presign_download(self, key: str, expires_in: int = 3600) -> str:
        """Generate a presigned URL for downloading a file.
        
        Args:
            key: The storage key/path for the file
            expires_in: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Presigned URL string
        """
        ...

