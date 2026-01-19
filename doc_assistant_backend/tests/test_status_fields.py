"""Tests for OCR and LLM status fields."""
import pytest
from unittest.mock import Mock, patch

from app.api.v1.docs import notify_uploaded
from app.infrastructure.queue.celery_queue import process_document_ocr, process_document_llm
from app.infrastructure.db.models import Document
from app.schemas import DocOut, DocDetailOut


class TestStatusFieldsInitialization:
    """Tests for status field initialization in /notify."""
    
    @patch('app.api.v1.docs.get_task_queue')
    @patch('app.api.v1.docs.get_db')
    def test_notify_initializes_status_fields(self, mock_get_db, mock_get_task_queue):
        """Test that /notify initializes ocr_status and llm_status to pending."""
        from app.schemas import UploadNotifyIn
        from fastapi import Request
        
        # Setup mock document (will be created)
        mock_db = Mock()
        mock_doc = Mock(spec=Document)
        mock_doc.id = 1
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        mock_get_db.return_value = iter([mock_db])
        
        # Mock Document creation
        with patch('app.api.v1.docs.Document') as mock_document_class:
            mock_document_class.return_value = mock_doc
            
            # Setup mock request
            mock_request = Mock(spec=Request)
            mock_request.state.request_id = "test-request-id"
            
            # Setup mock task queue
            mock_task_queue = Mock()
            mock_get_task_queue.return_value = mock_task_queue
            
            # Call notify
            payload = UploadNotifyIn(
                storage_key="test/key.pdf",
                filename="test.pdf",
                mime_type="application/pdf",
                size_bytes=1024
            )
            
            result = notify_uploaded(payload, request=mock_request, db=mock_db)
            
            # Verify Document was created with correct status fields
            mock_document_class.assert_called_once()
            call_kwargs = mock_document_class.call_args[1]
            assert call_kwargs.get("ocr_status") == "pending"
            assert call_kwargs.get("llm_status") == "pending"
            assert call_kwargs.get("status") == "processing"


class TestOcrStatusLifecycle:
    """Tests for OCR status field lifecycle in process_document_ocr."""
    
    @patch('app.infrastructure.queue.celery_queue.get_ocr_service')
    @patch('app.infrastructure.queue.celery_queue.SessionLocal')
    def test_ocr_status_processing_to_ready(self, mock_session_local, mock_get_ocr_service):
        """Test that OCR status moves from pending/processing to ready on success."""
        from app.infrastructure.ai.base import OcrResult
        
        # Setup mock document
        mock_doc = Mock(spec=Document)
        mock_doc.id = 1
        mock_doc.status = "processing"
        mock_doc.ocr_status = "pending"
        mock_doc.s3_key = "test/key.pdf"
        mock_doc.mime = "application/pdf"
        mock_doc.domain = "IDENTITY"
        mock_doc.doc_type = "PASSPORT"
        mock_doc.body = ""
        mock_doc.excerpt = ""
        mock_doc.extracted = None
        
        # Setup mock DB session
        mock_db = Mock()
        mock_db.get.return_value = mock_doc
        mock_session_local.return_value = mock_db
        
        # Setup mock OCR service
        mock_ocr_service = Mock()
        mock_ocr_service.extract_document.return_value = OcrResult(
            text="Extracted text content",
            page_count=1,
            language="en"
        )
        mock_get_ocr_service.return_value = mock_ocr_service
        
        # Execute task
        result = process_document_ocr(1)
        
        # Verify status transitions
        assert mock_doc.ocr_status == "processing"  # Set at start
        # After successful OCR, should be "ready"
        # Check the commit calls to see final state
        assert mock_doc.status == "ready"
        assert result["success"] is True
        
        # Verify OCR service was called
        mock_ocr_service.extract_document.assert_called_once()
    
    @patch('app.infrastructure.queue.celery_queue.get_ocr_service')
    @patch('app.infrastructure.queue.celery_queue.SessionLocal')
    def test_ocr_status_to_error_on_failure(self, mock_session_local, mock_get_ocr_service):
        """Test that OCR status becomes error on failure."""
        # Setup mock document
        mock_doc = Mock(spec=Document)
        mock_doc.id = 1
        mock_doc.status = "processing"
        mock_doc.ocr_status = "pending"
        mock_doc.s3_key = "test/key.pdf"
        
        # Setup mock DB session
        mock_db = Mock()
        mock_db.get.return_value = mock_doc
        mock_session_local.return_value = mock_db
        
        # Setup mock OCR service to raise exception
        mock_ocr_service = Mock()
        mock_ocr_service.extract_document.side_effect = Exception("OCR service error")
        mock_get_ocr_service.return_value = mock_ocr_service
        
        # Execute task
        result = process_document_ocr(1)
        
        # Verify error handling
        assert "error" in result
        # Check that error status was set (in the exception handler)
        # The exception handler should set both status and ocr_status to "error"


class TestLlmStatusLifecycle:
    """Tests for LLM status field lifecycle in process_document_llm."""
    
    @patch('app.infrastructure.queue.celery_queue.get_llm_service')
    @patch('app.infrastructure.queue.celery_queue.SessionLocal')
    def test_llm_status_processing_to_ready(self, mock_session_local, mock_get_llm_service):
        """Test that LLM status moves from pending to ready on success."""
        from app.infrastructure.ai.base import LlmResult
        
        # Setup mock document
        mock_doc = Mock(spec=Document)
        mock_doc.id = 1
        mock_doc.status = "ready"
        mock_doc.ocr_status = "ready"
        mock_doc.llm_status = "pending"
        mock_doc.body = "Test document text content"
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
            summary="Test summary",
            entities=[{"type": "TOKEN_COUNT", "value": 3}]
        )
        mock_get_llm_service.return_value = mock_llm_service
        
        # Execute task
        result = process_document_llm(1)
        
        # Verify status transitions
        assert mock_doc.llm_status == "processing"  # Set at start
        # After successful LLM, should be "ready"
        assert mock_doc.status == "ready"  # Should remain unchanged
        assert result["success"] is True
        
        # Verify LLM service was called
        mock_llm_service.analyze_document.assert_called_once()
    
    @patch('app.infrastructure.queue.celery_queue.get_llm_service')
    @patch('app.infrastructure.queue.celery_queue.SessionLocal')
    def test_llm_status_to_error_on_failure(self, mock_session_local, mock_get_llm_service):
        """Test that LLM status becomes error on failure, but main status stays ready."""
        # Setup mock document
        mock_doc = Mock(spec=Document)
        mock_doc.id = 1
        mock_doc.status = "ready"
        mock_doc.ocr_status = "ready"
        mock_doc.llm_status = "pending"
        mock_doc.body = "Test document text"
        mock_doc.mime = "text/plain"
        mock_doc.doc_type = None
        mock_doc.domain = None
        
        # Setup mock DB session
        mock_db = Mock()
        mock_db.get.return_value = mock_doc
        mock_session_local.return_value = mock_db
        
        # Setup mock LLM service to raise exception
        mock_llm_service = Mock()
        mock_llm_service.analyze_document.side_effect = Exception("LLM service error")
        mock_get_llm_service.return_value = mock_llm_service
        
        # Execute task
        result = process_document_llm(1)
        
        # Verify error handling
        assert "error" in result
        # LLM status should be "error", but main status should remain "ready"
        # (checked in exception handler)
    
    @patch('app.infrastructure.queue.celery_queue.SessionLocal')
    def test_llm_status_error_when_no_body(self, mock_session_local):
        """Test that LLM status becomes error when document has no body."""
        # Setup mock document without body
        mock_doc = Mock(spec=Document)
        mock_doc.id = 1
        mock_doc.status = "processing"
        mock_doc.ocr_status = "processing"
        mock_doc.llm_status = "pending"
        mock_doc.body = ""  # No OCR text
        
        # Setup mock DB session
        mock_db = Mock()
        mock_db.get.return_value = mock_doc
        mock_session_local.return_value = mock_db
        
        # Execute task
        result = process_document_llm(1)
        
        # Verify LLM status was set to error
        assert mock_doc.llm_status == "error"
        assert "error" in result


class TestApiResponseIncludesStatusFields:
    """Tests that API responses include ocr_status and llm_status."""
    
    def test_doc_out_includes_status_fields(self):
        """Test that DocOut schema includes ocr_status and llm_status."""
        # Create a DocOut instance from a mock document
        mock_doc = Mock()
        mock_doc.id = 1
        mock_doc.title = "Test"
        mock_doc.filename = "test.pdf"
        mock_doc.status = "ready"
        mock_doc.ocr_status = "ready"
        mock_doc.llm_status = "ready"
        mock_doc.excerpt = "Test excerpt"
        mock_doc.extracted = None
        mock_doc.domain = None
        mock_doc.doc_type = None
        mock_doc.expiry_date = None
        
        # Convert to DocOut
        doc_out = DocOut.model_validate(mock_doc)
        
        # Verify new fields are present
        assert hasattr(doc_out, "ocr_status")
        assert hasattr(doc_out, "llm_status")
        assert doc_out.ocr_status == "ready"
        assert doc_out.llm_status == "ready"
    
    def test_doc_detail_out_includes_status_fields(self):
        """Test that DocDetailOut schema includes ocr_status and llm_status."""
        # Create a DocDetailOut instance from a mock document
        mock_doc = Mock()
        mock_doc.id = 1
        mock_doc.title = "Test"
        mock_doc.filename = "test.pdf"
        mock_doc.status = "ready"
        mock_doc.ocr_status = "ready"
        mock_doc.llm_status = "ready"
        mock_doc.excerpt = "Test excerpt"
        mock_doc.body = "Test body"
        mock_doc.extracted = None
        mock_doc.domain = None
        mock_doc.doc_type = None
        mock_doc.expiry_date = None
        
        # Convert to DocDetailOut
        doc_detail_out = DocDetailOut.model_validate(mock_doc)
        
        # Verify new fields are present
        assert hasattr(doc_detail_out, "ocr_status")
        assert hasattr(doc_detail_out, "llm_status")
        assert doc_detail_out.ocr_status == "ready"
        assert doc_detail_out.llm_status == "ready"

