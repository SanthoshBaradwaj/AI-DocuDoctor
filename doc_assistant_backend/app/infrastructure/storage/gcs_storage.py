"""Google Cloud Storage implementation for StorageBackend protocol."""
import os
from datetime import timedelta
from typing import Dict, Any
from google.cloud import storage
from google.cloud.exceptions import NotFound
from google.auth import default
from google.auth.transport.requests import Request

from app.core.config import get_settings

settings = get_settings()


def get_gcs_bucket_name() -> str:
    """Get GCS bucket name from settings."""
    bucket = os.getenv("GCS_BUCKET") or settings.S3_BUCKET
    if not bucket:
        raise ValueError("GCS_BUCKET environment variable is required for GCS storage backend")
    return bucket


def make_gcs_client():
    """Create a GCS client using Application Default Credentials."""
    return storage.Client()


def presign_upload_v4(bucket_name: str, blob_name: str, content_type: str, expires_in: int = 600) -> Dict[str, Any]:
    """Generate a V4 signed URL for uploading to GCS.
    
    Args:
        bucket_name: GCS bucket name
        blob_name: Object path/key in bucket
        content_type: MIME type of the file
        expires_in: URL expiration time in seconds (default: 10 minutes)
        
    Returns:
        Dictionary with 'url', 'fields' (empty for V4), and 'key'
    """
    client = make_gcs_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    
    # Generate signed URL for PUT operation (upload)
    url = blob.generate_signed_url(
        version="v4",
        method="PUT",
        expiration=timedelta(seconds=expires_in),
        content_type=content_type,
    )
    
    return {
        "url": url,
        "fields": {},  # GCS V4 doesn't use fields like S3 POST
        "key": blob_name,
    }


def presign_download_v4(bucket_name: str, blob_name: str, expires_in: int = 3600) -> str:
    """Generate a V4 signed URL for downloading from GCS.
    
    Args:
        bucket_name: GCS bucket name
        blob_name: Object path/key in bucket
        expires_in: URL expiration time in seconds (default: 1 hour)
        
    Returns:
        Signed URL string
    """
    client = make_gcs_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    
    # Generate signed URL for GET operation (download)
    url = blob.generate_signed_url(
        version="v4",
        method="GET",
        expiration=timedelta(seconds=expires_in),
    )
    
    return url


def read_blob_bytes(bucket_name: str, blob_name: str) -> bytes:
    """Read blob content as bytes.
    
    Args:
        bucket_name: GCS bucket name
        blob_name: Object path/key in bucket
        
    Returns:
        Blob content as bytes
        
    Raises:
        NotFound: If blob doesn't exist
    """
    client = make_gcs_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    
    if not blob.exists():
        raise NotFound(f"Blob {blob_name} not found in bucket {bucket_name}")
    
    return blob.download_as_bytes()


def format_storage_key(key: str, bucket_name: str) -> str:
    """Format storage key as gs:// URL or return as-is if already formatted.
    
    Args:
        key: Storage key (object path or gs:// URL)
        bucket_name: GCS bucket name
        
    Returns:
        Storage key formatted as gs://bucket/object or object path
    """
    if key.startswith("gs://"):
        return key
    return f"gs://{bucket_name}/{key}"
