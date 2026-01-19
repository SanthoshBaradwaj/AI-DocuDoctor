"""Helper functions to read files from storage backends."""
from app.core.config import get_settings
from app.infrastructure.storage.gcs_storage import (
    get_gcs_bucket_name,
    read_blob_bytes,
)

settings = get_settings()


def read_text_file(storage_key: str) -> str:
    """Read a text file directly from storage (GCS or MinIO).
    
    Args:
        storage_key: Storage key (can be gs:// URL or object path)
        
    Returns:
        File content as UTF-8 text
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file cannot be read as text
    """
    storage_provider = getattr(settings, "STORAGE_PROVIDER", None) or settings.STORAGE_BACKEND
    
    if storage_provider == "gcs":
        # Parse storage key
        if storage_key.startswith("gs://"):
            # Extract bucket and object path
            parts = storage_key.replace("gs://", "").split("/", 1)
            bucket_name = parts[0]
            object_path = parts[1] if len(parts) > 1 else ""
        else:
            bucket_name = get_gcs_bucket_name()
            object_path = storage_key
        
        # Read from GCS
        from google.cloud.exceptions import NotFound
        try:
            bytes_content = read_blob_bytes(bucket_name, object_path)
            return bytes_content.decode('utf-8', errors='ignore')
        except NotFound:
            raise FileNotFoundError(f"File not found: {storage_key}")
    else:
        # MinIO/S3
        from app.infrastructure.storage.s3_minio import make_s3, get_bucket_name
        from botocore.exceptions import ClientError
        
        s3 = make_s3()
        bucket = get_bucket_name()
        
        try:
            obj = s3.get_object(Bucket=bucket, Key=storage_key)
            body_bytes = obj["Body"].read()
            return body_bytes.decode('utf-8', errors='ignore')
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'NoSuchKey':
                raise FileNotFoundError(f"File not found: {storage_key}")
            raise ValueError(f"Storage error: {error_code}")
