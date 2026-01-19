"""Tests for Celery LLM analysis task."""
import pytest
from unittest.mock import Mock, patch, MagicMock

from app.infrastructure.queue.celery_queue import process_document_llm
from app.infrastructure.db.models import Document
from app.infrastructure.ai.base import LlmResult


class TestProcessDocumentLlm:
    """Tests for process_document_llm Celery task."""
    
    @patch('app.infrastructure.queue.celery_queue.SessionLocal')
    @patch('app.infrastructure.queue.celery_queue.get_llm_service')
    def test_process_document_llm_success(self, mock_get_llm_service, mock_session_local):
        """Test successful LLM analysis task execution."""
        # Setup mock document
        mock_doc = Mock(spec=Document)
        mock_doc.id = 1
        mock_doc.body = "This is test document text content."
        mock_doc.status = "ready"
        mock_doc.mime = "text/plain"
        mock_doc.doc_type = "PASSPORT"
        mock_doc.domain = "IDENTITY"
        mock_doc.extracted = None
        
        # Setup mock DB session
        mock_db = Mock()
        mock_db.get.return_value = mock_doc
        mock_session_local.return_value = mock_db
        
        # Setup mock LLM service
        mock_llm_service = Mock()
        mock_llm_service.analyze_document.return_value = LlmResult(
            summary="Test summary [fake summary]",
            entities=[
                {"type": "TOKEN_COUNT", "value": 5},
                {"type": "DOC_TYPE", "value": "PASSPORT"},
            ]
        )
        mock_get_llm_service.return_value = mock_llm_service
        
        # Execute task
        result = process_document_llm(1)
        
        # Verify LLM service was called correctly
        mock_llm_service.analyze_document.assert_called_once_with(
            text="This is test document text content.",
            mime_type="text/plain",
            doc_type="PASSPORT",
        )
        
        # Verify document was updated
        assert mock_doc.extracted is not None
        assert mock_doc.extracted["summary"] == "Test summary [fake summary]"
        assert len(mock_doc.extracted["entities"]) == 2
        
        # Verify DB commit was called
        mock_db.commit.assert_called_once()
        
        # Verify result
        assert result["success"] is True
        assert result["document_id"] == 1
        
        # Verify DB was closed
        mock_db.close.assert_called_once()
    
    @patch('app.infrastructure.queue.celery_queue.SessionLocal')
    def test_process_document_llm_document_not_found(self, mock_session_local):
        """Test LLM task when document is not found."""
        mock_db = Mock()
        mock_db.get.return_value = None
        mock_session_local.return_value = mock_db
        
        result = process_document_llm(999)
        
        assert "error" in result
        assert "not found" in result["error"].lower()
        mock_db.close.assert_called_once()
    
    @patch('app.infrastructure.queue.celery_queue.SessionLocal')
    def test_process_document_llm_no_body(self, mock_session_local):
        """Test LLM task when document has no body (OCR not completed)."""
        mock_doc = Mock(spec=Document)
        mock_doc.id = 1
        mock_doc.body = ""
        mock_doc.status = "processing"
        
        mock_db = Mock()
        mock_db.get.return_value = mock_doc
        mock_session_local.return_value = mock_db
        
        result = process_document_llm(1)
        
        assert "error" in result
        assert "not ready" in result["error"].lower()
        mock_db.close.assert_called_once()
    
    @patch('app.infrastructure.queue.celery_queue.SessionLocal')
    def test_process_document_llm_status_not_ready(self, mock_session_local):
        """Test LLM task when document status is not 'ready'."""
        mock_doc = Mock(spec=Document)
        mock_doc.id = 1
        mock_doc.body = "Some text"
        mock_doc.status = "processing"
        
        mock_db = Mock()
        mock_db.get.return_value = mock_doc
        mock_session_local.return_value = mock_db
        
        result = process_document_llm(1)
        
        assert "error" in result
        assert "not ready" in result["error"].lower()
        mock_db.close.assert_called_once()
    
    @patch('app.infrastructure.queue.celery_queue.SessionLocal')
    @patch('app.infrastructure.queue.celery_queue.get_llm_service')
    def test_process_document_llm_llm_service_error(self, mock_get_llm_service, mock_session_local):
        """Test LLM task when LLM service raises an exception."""
        mock_doc = Mock(spec=Document)
        mock_doc.id = 1
        mock_doc.body = "Test text"
        mock_doc.status = "ready"
        mock_doc.mime = "text/plain"
        mock_doc.doc_type = None
        mock_doc.domain = None
        mock_doc.extracted = None
        
        mock_db = Mock()
        mock_db.get.return_value = mock_doc
        mock_session_local.return_value = mock_db
        
        # Setup LLM service to raise exception
        mock_llm_service = Mock()
        mock_llm_service.analyze_document.side_effect = Exception("LLM service error")
        mock_get_llm_service.return_value = mock_llm_service
        
        result = process_document_llm(1)
        
        assert "error" in result
        assert "LLM analysis failed" in result["error"]
        # Document should not be updated
        assert mock_doc.extracted is None
        mock_db.close.assert_called_once()

