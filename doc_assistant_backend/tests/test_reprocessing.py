"""Tests for document reprocessing endpoints."""
import pytest
from unittest.mock import Mock, patch, MagicMock

from app.api.v1.docs import reprocess_ocr, reprocess_llm
from app.infrastructure.db.models import Document
from fastapi import HTTPException


class TestReprocessOcr:
    """Tests for POST /api/v1/docs/{doc_id}/reprocess/ocr endpoint."""
    
    @patch('app.api.v1.docs.get_task_queue')
    @patch('app.api.v1.docs.get_db')
    def test_reprocess_ocr_success(self, mock_get_db, mock_get_task_queue):
        """Test successful OCR reprocessing."""
        # Setup mock document
        mock_doc = Mock(spec=Document)
        mock_doc.id = 1
        mock_doc.s3_key = "test/key.pdf"
        mock_doc.status = "ready"
        mock_doc.ocr_status = "ready"
        mock_doc.llm_status = "ready"
        
        # Setup mock DB session
        mock_db = Mock()
        mock_db.get.return_value = mock_doc
        mock_get_db.return_value = iter([mock_db])
        
        # Setup mock task queue
        mock_task_queue = Mock()
        mock_get_task_queue.return_value = mock_task_queue
        
        # Call endpoint
        result = reprocess_ocr(1, db=mock_db)
        
        # Verify document was updated
        assert mock_doc.status == "processing"
        assert mock_doc.ocr_status == "pending"
        assert mock_doc.llm_status == "pending"
        mock_db.commit.assert_called_once()
        
        # Verify OCR task was enqueued
        mock_task_queue.enqueue_ocr.assert_called_once_with(1)
        
        # Verify response
        assert result["message"] == "OCR reprocessing scheduled"
        assert result["document_id"] == 1
    
    @patch('app.api.v1.docs.get_db')
    def test_reprocess_ocr_document_not_found(self, mock_get_db):
        """Test OCR reprocessing when document doesn't exist."""
        mock_db = Mock()
        mock_db.get.return_value = None
        mock_get_db.return_value = iter([mock_db])
        
        with pytest.raises(HTTPException) as exc_info:
            reprocess_ocr(999, db=mock_db)
        
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()


class TestReprocessLlm:
    """Tests for POST /api/v1/docs/{doc_id}/reprocess/llm endpoint."""
    
    @patch('app.api.v1.docs.process_document_llm')
    @patch('app.api.v1.docs.get_db')
    def test_reprocess_llm_success(self, mock_get_db, mock_process_document_llm):
        """Test successful LLM reprocessing."""
        # Setup mock document
        mock_doc = Mock(spec=Document)
        mock_doc.id = 1
        mock_doc.body = "This is test document text content."
        mock_doc.llm_status = "ready"
        
        # Setup mock DB session
        mock_db = Mock()
        mock_db.get.return_value = mock_doc
        mock_get_db.return_value = iter([mock_db])
        
        # Setup mock Celery task
        mock_task = Mock()
        mock_task.delay = Mock(return_value=mock_task)
        mock_process_document_llm.delay = mock_task.delay
        
        # Call endpoint
        result = reprocess_llm(1, db=mock_db)
        
        # Verify document was updated
        assert mock_doc.llm_status == "pending"
        mock_db.commit.assert_called_once()
        
        # Verify LLM task was enqueued
        mock_process_document_llm.delay.assert_called_once_with(1)
        
        # Verify response
        assert result["message"] == "LLM reprocessing scheduled"
        assert result["document_id"] == 1
    
    @patch('app.api.v1.docs.get_db')
    def test_reprocess_llm_document_not_found(self, mock_get_db):
        """Test LLM reprocessing when document doesn't exist."""
        mock_db = Mock()
        mock_db.get.return_value = None
        mock_get_db.return_value = iter([mock_db])
        
        with pytest.raises(HTTPException) as exc_info:
            reprocess_llm(999, db=mock_db)
        
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()
    
    @patch('app.api.v1.docs.get_db')
    def test_reprocess_llm_no_body(self, mock_get_db):
        """Test LLM reprocessing when document has no body (OCR not completed)."""
        mock_doc = Mock(spec=Document)
        mock_doc.id = 1
        mock_doc.body = ""  # No OCR text
        
        mock_db = Mock()
        mock_db.get.return_value = mock_doc
        mock_get_db.return_value = iter([mock_db])
        
        with pytest.raises(HTTPException) as exc_info:
            reprocess_llm(1, db=mock_db)
        
        assert exc_info.value.status_code == 400
        assert "ocr not completed" in exc_info.value.detail.lower() or "no text content" in exc_info.value.detail.lower()

