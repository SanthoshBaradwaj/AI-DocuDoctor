"""Unit tests for GCS storage backend."""
import pytest
from unittest.mock import Mock, patch
from datetime import timedelta

from app.infrastructure.storage.gcs_backend import GCSStorageBackend
from app.infrastructure.storage.gcs_storage import (
    presign_upload_v4,
    presign_download_v4,
    format_storage_key,
)


@pytest.fixture
def mock_gcs_client():
    """Mock GCS client."""
    with patch('app.infrastructure.storage.gcs_storage.make_gcs_client') as mock:
        client = Mock()
        bucket = Mock()
        blob = Mock()
        
        client.bucket.return_value = bucket
        bucket.blob.return_value = blob
        blob.generate_signed_url.return_value = "https://storage.googleapis.com/..."
        blob.exists.return_value = True
        blob.download_as_bytes.return_value = b"test content"
        
        mock.return_value = client
        yield client, bucket, blob


class TestGCSStorageBackend:
    """Tests for GCSStorageBackend."""
    
    @patch('app.infrastructure.storage.gcs_backend.get_gcs_bucket_name')
    def test_presign_upload_with_object_path(self, mock_bucket):
        """Test presign_upload with object path."""
        mock_bucket.return_value = "test-bucket"
        backend = GCSStorageBackend()
        
        with patch('app.infrastructure.storage.gcs_backend.presign_upload_v4') as mock_presign:
            mock_presign.return_value = {
                "url": "https://storage.googleapis.com/...",
                "fields": {},
                "key": "user_1/doc.pdf"
            }
            
            result = backend.presign_upload("user_1/doc.pdf", "application/pdf")
            
            assert "url" in result
            assert "fields" in result
            assert "key" in result
            assert result["key"].startswith("gs://")
            mock_presign.assert_called_once_with(
                "test-bucket",
                "user_1/doc.pdf",
                "application/pdf"
            )
    
    @patch('app.infrastructure.storage.gcs_backend.get_gcs_bucket_name')
    def test_presign_upload_with_gs_url(self, mock_bucket):
        """Test presign_upload with gs:// URL."""
        mock_bucket.return_value = "test-bucket"
        backend = GCSStorageBackend()
        
        with patch('app.infrastructure.storage.gcs_backend.presign_upload_v4') as mock_presign:
            mock_presign.return_value = {
                "url": "https://storage.googleapis.com/...",
                "fields": {},
                "key": "user_1/doc.pdf"
            }
            
            result = backend.presign_upload("gs://test-bucket/user_1/doc.pdf", "application/pdf")
            
            assert result["key"].startswith("gs://")
            # Should extract object path from gs:// URL
            mock_presign.assert_called_once()
            call_args = mock_presign.call_args
            assert call_args[0][1] == "user_1/doc.pdf"  # Object path
    
    @patch('app.infrastructure.storage.gcs_backend.get_gcs_bucket_name')
    def test_presign_download(self, mock_bucket):
        """Test presign_download."""
        mock_bucket.return_value = "test-bucket"
        backend = GCSStorageBackend()
        
        with patch('app.infrastructure.storage.gcs_backend.presign_download_v4') as mock_presign:
            mock_presign.return_value = "https://storage.googleapis.com/..."
            
            result = backend.presign_download("user_1/doc.pdf")
            
            assert isinstance(result, str)
            assert result.startswith("https://")
            mock_presign.assert_called_once()


class TestGCSStorageHelpers:
    """Tests for GCS storage helper functions."""
    
    def test_format_storage_key_with_gs_url(self):
        """Test format_storage_key with gs:// URL."""
        result = format_storage_key("gs://bucket/path/to/file.pdf", "bucket")
        assert result == "gs://bucket/path/to/file.pdf"
    
    def test_format_storage_key_with_object_path(self):
        """Test format_storage_key with object path."""
        result = format_storage_key("path/to/file.pdf", "bucket")
        assert result == "gs://bucket/path/to/file.pdf"
