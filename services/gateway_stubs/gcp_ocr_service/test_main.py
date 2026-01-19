"""Unit tests for GCP OCR service."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

from main import app, parse_storage_key

client = TestClient(app)


class TestParseStorageKey:
    """Tests for storage_key parsing."""
    
    def test_parse_gs_url(self):
        """Test parsing gs:// URL."""
        bucket, object_path = parse_storage_key("gs://my-bucket/path/to/file.pdf")
        assert bucket == "my-bucket"
        assert object_path == "path/to/file.pdf"
    
    def test_parse_gs_url_with_root_path(self):
        """Test parsing gs:// URL with root path."""
        bucket, object_path = parse_storage_key("gs://my-bucket/file.pdf")
        assert bucket == "my-bucket"
        assert object_path == "file.pdf"
    
    def test_parse_object_path_only(self, monkeypatch):
        """Test parsing object path only (requires GCS_BUCKET env)."""
        monkeypatch.setenv("GCS_BUCKET", "my-bucket")
        # Re-import to pick up env var
        from main import parse_storage_key
        bucket, object_path = parse_storage_key("path/to/file.pdf")
        assert bucket == "my-bucket"
        assert object_path == "path/to/file.pdf"
    
    def test_parse_object_path_no_env(self):
        """Test parsing object path without GCS_BUCKET raises error."""
        import os
        # Temporarily remove GCS_BUCKET if set
        original = os.environ.get("GCS_BUCKET")
        if "GCS_BUCKET" in os.environ:
            del os.environ["GCS_BUCKET"]
        
        try:
            from main import parse_storage_key
            with pytest.raises(ValueError, match="GCS_BUCKET"):
                parse_storage_key("path/to/file.pdf")
        finally:
            if original:
                os.environ["GCS_BUCKET"] = original


class TestExtractEndpoint:
    """Tests for POST /extract endpoint."""
    
    def test_health_check(self):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    
    def test_missing_storage_key(self):
        """Test request with missing storage_key."""
        response = client.post(
            "/extract",
            json={"mime_type": "application/pdf"}
        )
        assert response.status_code == 422  # Pydantic validation error
    
    def test_empty_storage_key(self):
        """Test request with empty storage_key."""
        response = client.post(
            "/extract",
            json={"storage_key": "", "mime_type": "application/pdf"}
        )
        assert response.status_code == 400
    
    @patch('main.storage_client')
    @patch('main.vision_client')
    def test_text_file_extraction(self, mock_vision, mock_storage):
        """Test text file extraction (direct read from GCS)."""
        # Mock GCS blob
        mock_blob = Mock()
        mock_blob.download_as_text.return_value = "Test text content"
        mock_bucket = Mock()
        mock_bucket.blob.return_value = mock_blob
        mock_storage.bucket.return_value = mock_bucket
        
        response = client.post(
            "/extract",
            json={
                "storage_key": "gs://test-bucket/test.txt",
                "mime_type": "text/plain"
            },
            headers={"X-Request-ID": "test-123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "Test text content"
        assert data["page_count"] == 1
        assert data["language"] == "en"
    
    @patch('main.storage_client')
    def test_object_not_found(self, mock_storage):
        """Test 404 when object not found."""
        from google.api_core import exceptions as gcp_exceptions
        
        # Mock GCS blob to raise NotFound
        mock_blob = Mock()
        mock_blob.download_as_text.side_effect = gcp_exceptions.NotFound("Object not found")
        mock_bucket = Mock()
        mock_bucket.blob.return_value = mock_blob
        mock_storage.bucket.return_value = mock_bucket
        
        response = client.post(
            "/extract",
            json={
                "storage_key": "gs://test-bucket/missing.txt",
                "mime_type": "text/plain"
            }
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    @patch('main.extract_text_from_image_bytes')
    @patch('main.storage_client')
    def test_image_extraction(self, mock_storage, mock_extract):
        """Test image extraction using Vision API."""
        # Mock extract function
        mock_extract.return_value = ("Extracted text", 1, "en")
        
        # Mock GCS blob
        mock_blob = Mock()
        mock_blob.size = 1024  # 1KB
        mock_blob.download_as_bytes.return_value = b"fake image bytes"
        mock_bucket = Mock()
        mock_bucket.blob.return_value = mock_blob
        mock_storage.bucket.return_value = mock_bucket
        
        response = client.post(
            "/extract",
            json={
                "storage_key": "gs://test-bucket/image.jpg",
                "mime_type": "image/jpeg"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "Extracted text"
        assert data["page_count"] == 1
        assert data["language"] == "en"
    
    @patch('main.storage_client')
    def test_file_too_large(self, mock_storage):
        """Test 413 when file exceeds MAX_BYTES."""
        # Mock GCS blob with large size
        mock_blob = Mock()
        mock_blob.size = 20 * 1024 * 1024  # 20MB (exceeds default 10MB)
        mock_blob.reload = Mock()  # No-op
        mock_bucket = Mock()
        mock_bucket.blob.return_value = mock_blob
        mock_storage.bucket.return_value = mock_bucket
        
        response = client.post(
            "/extract",
            json={
                "storage_key": "gs://test-bucket/large-image.jpg",
                "mime_type": "image/jpeg"
            }
        )
        
        assert response.status_code == 413
        assert "exceeds maximum" in response.json()["detail"].lower()


class TestExtractTextFromImageBytes:
    """Tests for image text extraction."""
    
    @patch('main.vision_client')
    def test_extract_text_success(self, mock_vision_client):
        """Test successful text extraction from image."""
        from main import extract_text_from_image_bytes
        
        # Mock Vision API response
        mock_response = Mock()
        mock_response.error.message = ""
        mock_annotation = Mock()
        mock_annotation.text = "Extracted text from image"
        mock_page = Mock()
        mock_lang = Mock()
        mock_lang.language_code = "en"
        mock_page.property.detected_languages = [mock_lang]
        mock_annotation.pages = [mock_page]
        mock_response.full_text_annotation = mock_annotation
        mock_vision_client.text_detection.return_value = mock_response
        
        text, page_count, language = extract_text_from_image_bytes(b"fake image bytes")
        
        assert text == "Extracted text from image"
        assert page_count == 1
        assert language == "en"
    
    @patch('main.vision_client')
    def test_extract_text_error(self, mock_vision_client):
        """Test Vision API error handling."""
        from main import extract_text_from_image_bytes
        
        # Mock Vision API error
        mock_response = Mock()
        mock_response.error.message = "Vision API error"
        mock_vision_client.text_detection.return_value = mock_response
        
        with pytest.raises(RuntimeError, match="Vision API error"):
            extract_text_from_image_bytes(b"fake image bytes")

