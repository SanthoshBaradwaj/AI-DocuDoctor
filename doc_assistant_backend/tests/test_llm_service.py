"""Tests for LLM service implementations."""
import pytest
from unittest.mock import Mock, patch
import httpx

from app.infrastructure.ai.base import (
    LlmResult,
    FakeLLMService,
    HttpLlmService,
    get_llm_service,
)
from app.core.config import Settings


class TestFakeLLMService:
    """Tests for FakeLLMService."""
    
    def test_analyze_document_returns_llm_result(self):
        """Test that FakeLLMService.analyze_document returns LlmResult."""
        service = FakeLLMService()
        result = service.analyze_document(
            text="This is a test document with some content.",
            mime_type="text/plain",
            doc_type="PASSPORT"
        )
        
        assert isinstance(result, LlmResult)
        assert isinstance(result.summary, str)
        assert isinstance(result.entities, list)
        assert len(result.entities) > 0
    
    def test_analyze_document_generates_summary(self):
        """Test that analyze_document generates a summary."""
        service = FakeLLMService()
        test_text = "This is a test document with some content that should be summarized."
        result = service.analyze_document(text=test_text)
        
        assert result.summary
        assert "[fake summary]" in result.summary or len(result.summary) > 0
    
    def test_analyze_document_truncates_long_text(self):
        """Test that analyze_document truncates very long text in summary."""
        service = FakeLLMService()
        # Create text longer than 240 characters
        long_text = "A" * 300
        result = service.analyze_document(text=long_text)
        
        # Summary should be truncated (around 240 chars + suffix)
        assert len(result.summary) <= 260  # 240 + "… [fake summary]"
        assert "…" in result.summary or "[fake summary]" in result.summary
    
    def test_analyze_document_generates_entities(self):
        """Test that analyze_document generates entities."""
        service = FakeLLMService()
        test_text = "This is a test document."
        result = service.analyze_document(text=test_text)
        
        assert len(result.entities) > 0
        # Should have TOKEN_COUNT entity
        token_count_entity = next(
            (e for e in result.entities if e.get("type") == "TOKEN_COUNT"),
            None
        )
        assert token_count_entity is not None
        assert token_count_entity["value"] == len(test_text.split())
    
    def test_analyze_document_includes_doc_type_in_entities(self):
        """Test that doc_type is included in entities when provided."""
        service = FakeLLMService()
        result = service.analyze_document(
            text="Test document",
            doc_type="PASSPORT"
        )
        
        doc_type_entity = next(
            (e for e in result.entities if e.get("type") == "DOC_TYPE"),
            None
        )
        assert doc_type_entity is not None
        assert doc_type_entity["value"] == "PASSPORT"
    
    def test_analyze_document_without_doc_type(self):
        """Test that analyze_document works without doc_type."""
        service = FakeLLMService()
        result = service.analyze_document(text="Test document")
        
        assert result.summary
        assert result.entities
        # Should not have DOC_TYPE entity when not provided
        doc_type_entities = [e for e in result.entities if e.get("type") == "DOC_TYPE"]
        assert len(doc_type_entities) == 0
    
    def test_generate_still_works(self):
        """Test that the generate method still works for chat."""
        service = FakeLLMService()
        result = service.generate("Hello", context="Test context")
        
        assert isinstance(result, str)
        assert "Hello" in result or "dev mock" in result


class TestHttpLlmService:
    """Tests for HttpLlmService."""
    
    def test_analyze_document_success(self):
        """Test successful LLM analysis via HTTP."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "summary": "This is a test summary of the document.",
            "entities": [
                {"type": "TOKEN_COUNT", "value": 10},
                {"type": "DOC_TYPE", "value": "PASSPORT"},
            ]
        }
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        
        service = HttpLlmService(base_url="http://llm-service:8080", http_client=mock_client)
        result = service.analyze_document(
            text="This is a test document with some content.",
            mime_type="text/plain",
            doc_type="PASSPORT"
        )
        
        assert isinstance(result, LlmResult)
        assert result.summary == "This is a test summary of the document."
        assert len(result.entities) == 2
        assert result.entities[0]["type"] == "TOKEN_COUNT"
        assert result.entities[1]["type"] == "DOC_TYPE"
        
        # Verify HTTP call
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "http://llm-service:8080/analyze"
        assert call_args[1]["json"]["text"] == "This is a test document with some content."
        assert call_args[1]["json"]["mime_type"] == "text/plain"
        assert call_args[1]["json"]["doc_type"] == "PASSPORT"
    
    def test_analyze_document_without_optional_fields(self):
        """Test HTTP LLM analysis without optional fields."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "summary": "Test summary",
            "entities": []
        }
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        
        service = HttpLlmService(base_url="http://llm-service:8080", http_client=mock_client)
        result = service.analyze_document(text="Test document")
        
        assert result.summary == "Test summary"
        assert result.entities == []
        
        # Verify mime_type and doc_type not in payload
        call_args = mock_client.post.call_args
        assert "mime_type" not in call_args[1]["json"]
        assert "doc_type" not in call_args[1]["json"]
    
    def test_analyze_document_http_error(self):
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
        
        service = HttpLlmService(base_url="http://llm-service:8080", http_client=mock_client)
        
        with pytest.raises(httpx.HTTPStatusError):
            service.analyze_document(text="Test document")
    
    def test_analyze_document_invalid_response_format(self):
        """Test handling of invalid response format."""
        mock_response = Mock()
        mock_response.json.return_value = "not a dict"
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        
        service = HttpLlmService(base_url="http://llm-service:8080", http_client=mock_client)
        
        with pytest.raises(ValueError, match="Invalid response format"):
            service.analyze_document(text="Test document")
    
    def test_analyze_document_missing_summary_field(self):
        """Test handling of response missing summary field."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "entities": [{"type": "TOKEN_COUNT", "value": 5}]
        }
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        
        service = HttpLlmService(base_url="http://llm-service:8080", http_client=mock_client)
        
        with pytest.raises(ValueError, match="missing 'summary' field"):
            service.analyze_document(text="Test document")
    
    def test_analyze_document_invalid_summary_type(self):
        """Test handling of invalid summary type."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "summary": 123,  # Should be string
            "entities": []
        }
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        
        service = HttpLlmService(base_url="http://llm-service:8080", http_client=mock_client)
        
        with pytest.raises(ValueError, match="'summary' must be a string"):
            service.analyze_document(text="Test document")
    
    def test_analyze_document_invalid_entities_type(self):
        """Test handling of invalid entities type."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "summary": "Test summary",
            "entities": "not a list"  # Should be list
        }
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        
        service = HttpLlmService(base_url="http://llm-service:8080", http_client=mock_client)
        
        with pytest.raises(ValueError, match="'entities' must be a list"):
            service.analyze_document(text="Test document")
    
    def test_analyze_document_request_error(self):
        """Test handling of request errors (network, timeout, etc.)."""
        mock_client = Mock()
        mock_client.post.side_effect = httpx.RequestError("Connection failed", request=Mock())
        
        service = HttpLlmService(base_url="http://llm-service:8080", http_client=mock_client)
        
        with pytest.raises(httpx.RequestError):
            service.analyze_document(text="Test document")


class TestGetLlmService:
    """Tests for get_llm_service factory function."""
    
    @patch('app.infrastructure.ai.base.get_settings')
    def test_get_llm_service_returns_fake(self, mock_get_settings):
        """Test that get_llm_service returns FakeLLMService when LLM_PROVIDER is 'fake'."""
        mock_settings = Mock(spec=Settings)
        mock_settings.LLM_PROVIDER = "fake"
        mock_get_settings.return_value = mock_settings
        
        service = get_llm_service()
        
        assert isinstance(service, FakeLLMService)
    
    @patch('app.infrastructure.ai.base.get_settings')
    def test_get_llm_service_returns_http(self, mock_get_settings):
        """Test that get_llm_service returns HttpLlmService when LLM_PROVIDER is 'http'."""
        mock_settings = Mock(spec=Settings)
        mock_settings.LLM_PROVIDER = "http"
        mock_settings.LLM_SERVICE_URL = "http://llm-service:8080"
        mock_get_settings.return_value = mock_settings
        
        service = get_llm_service()
        
        assert isinstance(service, HttpLlmService)
        assert service.base_url == "http://llm-service:8080"
    
    @patch('app.infrastructure.ai.base.get_settings')
    def test_get_llm_service_raises_error_when_http_provider_missing_url(self, mock_get_settings):
        """Test that get_llm_service raises error when LLM_PROVIDER is 'http' but URL is missing."""
        mock_settings = Mock(spec=Settings)
        mock_settings.LLM_PROVIDER = "http"
        mock_settings.LLM_SERVICE_URL = None
        mock_get_settings.return_value = mock_settings
        
        with pytest.raises(RuntimeError, match="LLM_SERVICE_URL is not configured"):
            get_llm_service()
    
    @patch('app.infrastructure.ai.base.get_settings')
    def test_get_llm_service_raises_error_for_unsupported_provider(self, mock_get_settings):
        """Test that get_llm_service raises error for unsupported LLM_PROVIDER."""
        mock_settings = Mock(spec=Settings)
        mock_settings.LLM_PROVIDER = "unsupported"
        mock_get_settings.return_value = mock_settings
        
        with pytest.raises(RuntimeError, match="Unsupported LLM_PROVIDER"):
            get_llm_service()

