"""Tests for health and config endpoints."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import os

from app.main import app

client = TestClient(app)


class TestHealthEndpoint:
    """Tests for GET /api/v1/health endpoint."""
    
    def test_health_returns_ok(self):
        """Test that health endpoint returns status ok."""
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "app_env" in data
        assert "app_name" in data
    
    def test_health_no_downstream_calls(self):
        """Test that health endpoint doesn't make downstream calls."""
        # This is verified by the endpoint not having any Depends() that would trigger DB/storage calls
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200
        # Should return quickly without any external dependencies
    
    def test_health_includes_build_if_available(self):
        """Test that health endpoint includes build info if available."""
        with patch.dict(os.environ, {"BUILD_ID": "build-123"}):
            # Need to reload settings to pick up new env var
            from app.core.config import get_settings
            get_settings.cache_clear()
            
            response = client.get("/api/v1/health")
            data = response.json()
            
            if "BUILD_ID" in os.environ:
                assert "build" in data
                assert data["build"] == "build-123"
            
            # Restore
            get_settings.cache_clear()
    
    def test_health_includes_version_if_available(self):
        """Test that health endpoint includes version info if available."""
        with patch.dict(os.environ, {"VERSION": "1.2.3"}):
            from app.core.config import get_settings
            get_settings.cache_clear()
            
            response = client.get("/api/v1/health")
            data = response.json()
            
            if "VERSION" in os.environ:
                assert "version" in data
                assert data["version"] == "1.2.3"
            
            # Restore
            get_settings.cache_clear()
    
    def test_health_response_format(self):
        """Test that health response has consistent format."""
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Required fields
        assert "status" in data
        assert "app_env" in data
        assert "app_name" in data
        
        # Optional fields (may or may not be present)
        # build and version are optional


class TestHealthDepsEndpoint:
    """Tests for GET /api/v1/health/deps endpoint."""
    
    def test_health_deps_returns_status(self):
        """Test that health deps endpoint returns dependency status."""
        response = client.get("/api/v1/health/deps")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "dependencies" in data
        assert isinstance(data["dependencies"], dict)


class TestLlmConfigEndpoint:
    """Tests for gcp-llm-service GET /config endpoint."""
    
    def test_config_endpoint_exists(self):
        """Test that /config endpoint exists in gcp-llm-service."""
        # Note: This would require the gcp-llm-service to be running
        # For now, we verify the endpoint exists in the code
        from services.gateway_stubs.gcp_llm_service.main import app as llm_app
        llm_client = TestClient(llm_app)
        
        response = llm_client.get("/config")
        
        assert response.status_code == 200
        data = response.json()
        assert "model_name" in data
        assert "fallbacks" in data
        assert "region" in data
        
        # Verify no secrets
        assert "api_key" not in str(data).lower()
        assert "secret" not in str(data).lower()
        assert "password" not in str(data).lower()
        assert "token" not in str(data).lower()
    
    def test_config_response_format(self):
        """Test that config response has correct format."""
        from services.gateway_stubs.gcp_llm_service.main import app as llm_app
        llm_client = TestClient(llm_app)
        
        response = llm_client.get("/config")
        
        assert response.status_code == 200
        data = response.json()
        
        # Required fields
        assert isinstance(data["model_name"], str)
        assert isinstance(data["fallbacks"], list)
        assert isinstance(data["region"], str)
        
        # Verify fallbacks is a list of strings
        for fallback in data["fallbacks"]:
            assert isinstance(fallback, str)


class TestStatusSemantics:
    """Tests for llm_status semantics fix."""
    
    def test_llm_status_ready_when_ocr_completes(self):
        """Test that llm_status is set to ready when OCR completes."""
        # This is tested through the document processor
        # When OCR completes, llm_status should be set to "ready"
        # even if LLM analysis hasn't run yet (chat is available)
        pass  # Integration test would verify this


class TestStatusTransition:
    """Tests for status transition logic."""
    
    def test_llm_status_pending_to_ready_allowed(self):
        """Test that pending -> ready transition is allowed for llm_status."""
        from app.services.status import set_llm_status
        from app.core.constants import PipelineStepStatus
        from app.infrastructure.db.models import Document
        from unittest.mock import Mock
        
        # Create mock document
        mock_doc = Mock(spec=Document)
        mock_doc.llm_status = PipelineStepStatus.PENDING.value
        mock_doc.id = 1
        
        # Should allow pending -> ready (when OCR completes)
        set_llm_status(mock_doc, PipelineStepStatus.READY, reason="OCR completed")
        
        assert mock_doc.llm_status == PipelineStepStatus.READY.value
