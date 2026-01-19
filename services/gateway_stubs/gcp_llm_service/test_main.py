"""Unit tests for GCP LLM Gateway Service."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
import json

from main import (
    app,
    AnalyzeRequest,
    AnalyzeResponse,
    count_tokens_approx,
    extract_json_from_text,
    build_prompt,
)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_gemini_response():
    """Mock Gemini response."""
    return {
        "text": json.dumps({
            "summary": "This is a test summary",
            "entities": [
                {"type": "DATE", "value": "2024-01-15"},
                {"type": "AMOUNT", "value": "1000"}
            ]
        })
    }


class TestTokenCounting:
    """Tests for token counting."""
    
    def test_count_tokens_approx(self):
        """Test approximate token counting."""
        text = "This is a test document with multiple words"
        assert count_tokens_approx(text) == 8
        
        text_empty = ""
        assert count_tokens_approx(text_empty) == 0
        
        text_multiline = "Line 1\nLine 2\nLine 3"
        assert count_tokens_approx(text_multiline) == 6


class TestJSONExtraction:
    """Tests for JSON extraction from text."""
    
    def test_extract_json_from_markdown_block(self):
        """Test extracting JSON from markdown code block."""
        text = "```json\n{\"summary\": \"test\", \"entities\": []}\n```"
        result = extract_json_from_text(text)
        assert result is not None
        assert result["summary"] == "test"
        assert result["entities"] == []
    
    def test_extract_json_from_plain_json(self):
        """Test extracting JSON from plain text."""
        text = '{"summary": "test", "entities": [{"type": "A", "value": "B"}]}'
        result = extract_json_from_text(text)
        assert result is not None
        assert result["summary"] == "test"
        assert len(result["entities"]) == 1
    
    def test_extract_json_fails_on_invalid(self):
        """Test that invalid JSON returns None."""
        text = "This is not JSON at all"
        result = extract_json_from_text(text)
        assert result is None


class TestPromptBuilding:
    """Tests for prompt building."""
    
    def test_build_prompt_without_doc_type(self):
        """Test building prompt without doc_type."""
        text = "Test document text"
        prompt = build_prompt(text, None)
        assert "Test document text" in prompt
        assert "Note: This document is of type" not in prompt
        assert "JSON" in prompt
    
    def test_build_prompt_with_doc_type(self):
        """Test building prompt with doc_type."""
        text = "Test document text"
        prompt = build_prompt(text, "PASSPORT")
        assert "Test document text" in prompt
        assert "PASSPORT" in prompt
        assert "Note: This document is of type" in prompt


class TestAnalyzeEndpoint:
    """Tests for /analyze endpoint."""
    
    def test_analyze_missing_text(self, client):
        """Test analyze with missing text."""
        response = client.post("/analyze", json={})
        assert response.status_code == 422  # Validation error
    
    def test_analyze_empty_text(self, client):
        """Test analyze with empty text."""
        response = client.post("/analyze", json={"text": ""})
        assert response.status_code == 400
        assert "cannot be empty" in response.json()["detail"]
    
    def test_analyze_text_too_long(self, client):
        """Test analyze with text exceeding MAX_CHARS."""
        long_text = "x" * 60000
        response = client.post("/analyze", json={"text": long_text})
        assert response.status_code == 413
        assert "exceeds maximum" in response.json()["detail"]
    
    @patch('main.call_gemini_async')
    def test_analyze_success(self, mock_call, client, mock_gemini_response):
        """Test successful analyze request."""
        # Mock Gemini response
        mock_call.return_value = {
            "summary": "Test summary",
            "entities": [
                {"type": "DATE", "value": "2024-01-15"}
            ]
        }
        
        response = client.post(
            "/analyze",
            json={
                "text": "This is a test document.",
                "doc_type": "PASSPORT",
                "mime_type": "text/plain"
            },
            headers={"X-Request-ID": "test-request-123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "entities" in data
        assert isinstance(data["entities"], list)
        
        # Check that TOKEN_COUNT is included
        token_count_entity = next(
            (e for e in data["entities"] if e["type"] == "TOKEN_COUNT"),
            None
        )
        assert token_count_entity is not None
        assert token_count_entity["value"] > 0
        
        # Check that DOC_TYPE is included
        doc_type_entity = next(
            (e for e in data["entities"] if e["type"] == "DOC_TYPE"),
            None
        )
        assert doc_type_entity is not None
        assert doc_type_entity["value"] == "PASSPORT"
    
    @patch('main.call_gemini_async')
    def test_analyze_without_doc_type(self, mock_call, client):
        """Test analyze without doc_type."""
        mock_call.return_value = {
            "summary": "Test summary",
            "entities": []
        }
        
        response = client.post(
            "/analyze",
            json={"text": "This is a test document."}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # TOKEN_COUNT should be present
        token_count_entity = next(
            (e for e in data["entities"] if e["type"] == "TOKEN_COUNT"),
            None
        )
        assert token_count_entity is not None
        
        # DOC_TYPE should NOT be present
        doc_type_entity = next(
            (e for e in data["entities"] if e["type"] == "DOC_TYPE"),
            None
        )
        assert doc_type_entity is None
    
    @patch('main.call_gemini_async')
    def test_analyze_timeout(self, mock_call, client):
        """Test analyze with timeout error."""
        import asyncio
        mock_call.side_effect = TimeoutError("Request timed out")
        
        response = client.post(
            "/analyze",
            json={"text": "This is a test document."}
        )
        
        assert response.status_code == 504
        assert "timed out" in response.json()["detail"]
    
    @patch('main.call_gemini_async')
    def test_analyze_vertex_error(self, mock_call, client):
        """Test analyze with Vertex AI error."""
        from google.api_core import exceptions as gcp_exceptions
        mock_call.side_effect = RuntimeError("Vertex AI API error: Permission denied")
        
        response = client.post(
            "/analyze",
            json={"text": "This is a test document."}
        )
        
        assert response.status_code == 502
        assert "Vertex AI" in response.json()["detail"]


class TestHealthEndpoint:
    """Tests for /health endpoint."""
    
    def test_health(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "model" in data
        assert "region" in data


class TestGeminiCall:
    """Tests for Gemini API calls (mocked)."""
    
    @pytest.mark.asyncio
    @patch('main.GenerativeModel')
    async def test_call_gemini_async_success(self, mock_model_class):
        """Test successful Gemini call."""
        from main import call_gemini_async
        
        # Mock model and response
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = json.dumps({
            "summary": "Test summary",
            "entities": [{"type": "A", "value": "B"}]
        })
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model
        
        result = await call_gemini_async("Test text", "PASSPORT")
        
        assert "summary" in result
        assert "entities" in result
        assert result["summary"] == "Test summary"
        assert len(result["entities"]) == 1
    
    @pytest.mark.asyncio
    @patch('main.GenerativeModel')
    async def test_call_gemini_async_fallback(self, mock_model_class):
        """Test Gemini call with JSON parsing fallback."""
        from main import call_gemini_async
        
        # Mock model returning non-JSON text
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "This is a plain text response without JSON"
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model
        
        result = await call_gemini_async("Test text")
        
        assert "summary" in result
        assert len(result["summary"]) > 0
        assert "entities" in result
        assert isinstance(result["entities"], list)
    
    @pytest.mark.asyncio
    async def test_call_gemini_async_timeout(self):
        """Test Gemini call timeout."""
        from main import call_gemini_async
        import asyncio
        
        # Mock executor to simulate timeout
        with patch('main.asyncio.wait_for') as mock_wait:
            mock_wait.side_effect = asyncio.TimeoutError()
            
            with pytest.raises(TimeoutError):
                await call_gemini_async("Test text")
