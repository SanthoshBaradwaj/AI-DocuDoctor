"""Tests for OCR service implementations."""
import pytest
from unittest.mock import Mock, patch, MagicMock
import httpx

from app.infrastructure.ai.base import (
    OcrResult,
    FakeOcrService,
    HttpOcrService,
    get_ocr_service,
)
from app.core.config import Settings


class TestFakeOcrService:
    """Tests for FakeOcrService."""
    
    def test_extract_document_returns_ocr_result(self):
        """Test that FakeOcrService returns OcrResult."""
        service = FakeOcrService()
        result = service.extract_document(
            storage_key="test/file.txt",
            mime_type="text/plain"
        )
        
        assert isinstance(result, OcrResult)
        assert isinstance(result.text, str)
        assert result.page_count == 1
        assert result.language == "en"
    
    def test_extract_document_includes_storage_key_in_text(self):
        """Test that storage key is included in fake text."""
        service = FakeOcrService()
        result = service.extract_document(
            storage_key="test/document.pdf"
        )
        
        assert "test/document.pdf" in result.text
    
    def test_extract_document_includes_mime_type_when_provided(self):
        """Test that MIME type is included when provided."""
        service = FakeOcrService()
        result = service.extract_document(
            storage_key="test/file.pdf",
            mime_type="application/pdf"
        )
        
        assert "application/pdf" in result.text


class TestHttpOcrService:
    """Tests for HttpOcrService."""
    
    def test_extract_document_success(self):
        """Test successful OCR extraction via HTTP."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "text": "Extracted text from document",
            "page_count": 3,
            "language": "en"
        }
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        
        service = HttpOcrService(base_url="http://ocr-service:8080", http_client=mock_client)
        result = service.extract_document(
            storage_key="test/document.pdf",
            mime_type="application/pdf"
        )
        
        assert isinstance(result, OcrResult)
        assert result.text == "Extracted text from document"
        assert result.page_count == 3
        assert result.language == "en"
        
        # Verify HTTP call
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "http://ocr-service:8080/extract"
        assert call_args[1]["json"]["storage_key"] == "test/document.pdf"
        assert call_args[1]["json"]["mime_type"] == "application/pdf"
    
    def test_extract_document_without_mime_type(self):
        """Test HTTP OCR extraction without MIME type."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "text": "Extracted text",
            "page_count": 1,
        }
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        
        service = HttpOcrService(base_url="http://ocr-service:8080", http_client=mock_client)
        result = service.extract_document(storage_key="test/file.pdf")
        
        assert result.text == "Extracted text"
        assert result.page_count == 1
        assert result.language is None
        
        # Verify mime_type not in payload
        call_args = mock_client.post.call_args
        assert "mime_type" not in call_args[1]["json"]
    
    def test_extract_document_http_error(self):
        """Test handling of HTTP errors."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error",
            request=Mock(),
            response=mock_response
        )
        
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        
        service = HttpOcrService(base_url="http://ocr-service:8080", http_client=mock_client)
        
        with pytest.raises(httpx.HTTPStatusError):
            service.extract_document(storage_key="test/file.pdf")
    
    def test_extract_document_invalid_response_format(self):
        """Test handling of invalid response format."""
        mock_response = Mock()
        mock_response.json.return_value = "not a dict"
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        
        service = HttpOcrService(base_url="http://ocr-service:8080", http_client=mock_client)
        
        with pytest.raises(ValueError, match="Invalid response format"):
            service.extract_document(storage_key="test/file.pdf")
    
    def test_extract_document_missing_text_field(self):
        """Test handling of response missing text field."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "page_count": 1,
            "language": "en"
        }
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        
        service = HttpOcrService(base_url="http://ocr-service:8080", http_client=mock_client)
        
        with pytest.raises(ValueError, match="missing 'text' field"):
            service.extract_document(storage_key="test/file.pdf")
    
    def test_extract_document_request_error(self):
        """Test handling of request errors (network, timeout, etc.)."""
        mock_client = Mock()
        mock_client.post.side_effect = httpx.RequestError("Connection failed", request=Mock())
        
        service = HttpOcrService(base_url="http://ocr-service:8080", http_client=mock_client)
        
        with pytest.raises(httpx.RequestError):
            service.extract_document(storage_key="test/file.pdf")


class TestGetOcrService:
    """Tests for get_ocr_service factory function."""
    
    @patch('app.infrastructure.ai.base.get_settings')
    def test_get_ocr_service_returns_fake_when_provider_is_fake(self, mock_get_settings):
        """Test that get_ocr_service returns FakeOcrService when OCR_PROVIDER is 'fake'."""
        mock_settings = Mock(spec=Settings)
        mock_settings.OCR_PROVIDER = "fake"
        mock_get_settings.return_value = mock_settings
        
        service = get_ocr_service()
        
        assert isinstance(service, FakeOcrService)
    
    @patch('app.infrastructure.ai.base.get_settings')
    def test_get_ocr_service_returns_http_when_provider_is_http(self, mock_get_settings):
        """Test that get_ocr_service returns HttpOcrService when OCR_PROVIDER is 'http'."""
        mock_settings = Mock(spec=Settings)
        mock_settings.OCR_PROVIDER = "http"
        mock_settings.OCR_SERVICE_URL = "http://ocr-service:8080"
        mock_get_settings.return_value = mock_settings
        
        service = get_ocr_service()
        
        assert isinstance(service, HttpOcrService)
        assert service.base_url == "http://ocr-service:8080"
    
    @patch('app.infrastructure.ai.base.get_settings')
    def test_get_ocr_service_raises_error_when_http_provider_missing_url(self, mock_get_settings):
        """Test that get_ocr_service raises error when OCR_PROVIDER is 'http' but URL is missing."""
        mock_settings = Mock(spec=Settings)
        mock_settings.OCR_PROVIDER = "http"
        mock_settings.OCR_SERVICE_URL = None
        mock_get_settings.return_value = mock_settings
        
        with pytest.raises(ValueError, match="OCR_SERVICE_URL is not configured"):
            get_ocr_service()
    
    @patch('app.infrastructure.ai.base.get_settings')
    def test_get_ocr_service_raises_error_for_unsupported_provider(self, mock_get_settings):
        """Test that get_ocr_service raises error for unsupported OCR_PROVIDER."""
        mock_settings = Mock(spec=Settings)
        mock_settings.OCR_PROVIDER = "unsupported"
        mock_get_settings.return_value = mock_settings
        
        with pytest.raises(ValueError, match="Unsupported OCR_PROVIDER"):
            get_ocr_service()

