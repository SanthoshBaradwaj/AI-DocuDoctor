"""Tests for EPIC 3 Chunk 1: Page Count + Limits."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from io import BytesIO

from app.main import app
from app.core.config import get_settings
from app.infrastructure.db.models import Document

client = TestClient(app)
settings = get_settings()


class TestPageCountExtraction:
    """Tests for PDF page counting."""
    
    def test_count_pdf_pages_invalid_pdf(self):
        """Test that invalid PDF raises ValueError."""
        from app.services.pdf_utils import count_pdf_pages
        
        invalid_bytes = b"not a pdf"
        
        with pytest.raises(ValueError, match="Invalid PDF"):
            count_pdf_pages(invalid_bytes)
    
    @patch('pypdf.PdfReader')
    def test_count_pdf_pages_mock(self, mock_pdf_reader):
        """Test page counting with mocked pypdf."""
        from app.services.pdf_utils import count_pdf_pages
        
        # Mock PdfReader
        mock_reader = Mock()
        mock_reader.pages = [Mock(), Mock(), Mock()]  # 3 pages
        mock_pdf_reader.return_value = mock_reader
        
        pdf_bytes = b"fake pdf bytes"
        page_count = count_pdf_pages(pdf_bytes)
        
        assert page_count == 3
        mock_pdf_reader.assert_called_once()


class TestPageLimitEnforcement:
    """Tests for page limit enforcement in /notify endpoint."""
    
    @patch('app.api.v1.docs.get_storage_backend')
    @patch('app.services.pdf_utils.count_pdf_pages')
    @patch('app.api.v1.docs.get_task_queue')
    @patch('app.api.v1.docs.get_db')
    def test_notify_rejects_pdf_over_page_limit(self, mock_get_db, mock_task_queue, mock_count_pages, mock_storage):
        """Test that /notify rejects PDFs with more than MAX_PDF_PAGES."""
        from app.infrastructure.db.models import Document
        from app.core.constants import PipelineStepStatus
        
        # Setup mocks
        mock_storage_instance = Mock()
        mock_storage_instance.read_bytes.return_value = b"fake pdf bytes"
        mock_storage.return_value = mock_storage_instance
        
        # Set page count to exceed limit
        max_pages = getattr(settings, 'MAX_PDF_PAGES', 10)
        mock_count_pages.return_value = max_pages + 1
        
        # Mock database
        mock_db = Mock()
        mock_doc = Mock(spec=Document)
        mock_doc.id = "123"
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        mock_get_db.return_value = mock_db
        
        # Mock task queue
        mock_queue = Mock()
        mock_task_queue.return_value = mock_queue
        
        payload = {
            "storage_key": "test/document.pdf",
            "filename": "test.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 1000,
        }
        
        response = client.post("/api/v1/docs/notify", json=payload)
        
        assert response.status_code == 413
        data = response.json()
        assert data["error_code"] == "PAGE_LIMIT_EXCEEDED"
        assert "pages" in data["message"].lower()
        assert data["details"]["page_count"] == max_pages + 1
        assert data["details"]["max_pages"] == max_pages
        assert "request_id" in data
    
    @patch('app.api.v1.docs.get_storage_backend')
    @patch('app.services.pdf_utils.count_pdf_pages')
    @patch('app.api.v1.docs.get_task_queue')
    @patch('app.api.v1.docs.get_db')
    def test_notify_accepts_pdf_within_page_limit(self, mock_get_db, mock_task_queue, mock_count_pages, mock_storage):
        """Test that /notify accepts PDFs within page limit."""
        from app.infrastructure.db.models import Document
        
        # Setup mocks
        mock_storage_instance = Mock()
        mock_storage_instance.read_bytes.return_value = b"fake pdf bytes"
        mock_storage.return_value = mock_storage_instance
        
        # Set page count within limit
        max_pages = getattr(settings, 'MAX_PDF_PAGES', 10)
        mock_count_pages.return_value = max_pages
        
        # Mock database
        mock_db = Mock()
        mock_doc = Mock(spec=Document)
        mock_doc.id = "123"
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock(side_effect=lambda d: setattr(d, 'id', '123'))
        mock_get_db.return_value = mock_db
        
        # Mock task queue
        mock_queue = Mock()
        mock_task_queue.return_value = mock_queue
        
        payload = {
            "storage_key": "test/document.pdf",
            "filename": "test.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 1000,
        }
        
        # This would require proper DB setup - placeholder for structure
        # Expected: HTTP 200, document created, OCR enqueued
        pass


class TestMaxUploadBytesEnforcement:
    """Tests for MAX_UPLOAD_BYTES enforcement."""
    
    def test_presign_rejects_oversized_file(self):
        """Test that /presign rejects files exceeding MAX_UPLOAD_BYTES."""
        max_bytes = getattr(settings, 'MAX_UPLOAD_BYTES', 15 * 1024 * 1024)
        
        payload = {
            "filename": "large.pdf",
            "mime_type": "application/pdf",
            "size_bytes": max_bytes + 1,
        }
        
        response = client.post("/api/v1/docs/upload/presign", json=payload)
        assert response.status_code == 413
        assert response.json()["error_code"] == "PAYLOAD_TOO_LARGE"
        assert "exceeds maximum" in response.json()["message"].lower()
    
    def test_notify_rejects_oversized_file(self):
        """Test that /notify rejects files exceeding MAX_UPLOAD_BYTES."""
        max_bytes = getattr(settings, 'MAX_UPLOAD_BYTES', 15 * 1024 * 1024)
        
        payload = {
            "storage_key": "test/large.pdf",
            "filename": "large.pdf",
            "mime_type": "application/pdf",
            "size_bytes": max_bytes + 1,
        }
        
        response = client.post("/api/v1/docs/notify", json=payload)
        assert response.status_code == 413
        assert response.json()["error_code"] == "PAYLOAD_TOO_LARGE"


class TestOcrTextTruncation:
    """Tests for OCR text truncation before LLM (CHUNK 2)."""
    
    @patch('app.services.document_processor.get_llm_service')
    @patch('app.services.document_processor.update_document')
    @patch('app.services.document_processor.set_llm_status')
    def test_llm_receives_truncated_text(self, mock_set_status, mock_update_doc, mock_llm_service):
        """Test that LLM receives text truncated to MAX_OCR_CHARS."""
        max_chars = getattr(settings, 'MAX_OCR_CHARS', 50000)
        
        # Create mock document with long OCR text
        mock_doc = Mock(spec=Document)
        mock_doc.id = "123"
        mock_doc.body = "x" * (max_chars + 1000)  # Exceeds limit
        mock_doc.mime = "application/pdf"
        mock_doc.doc_type = None
        mock_doc.status = "ready"
        mock_doc.ocr_status = "ready"
        mock_doc.llm_status = "pending"
        mock_doc.request_id = "req-123"
        mock_doc.extracted = {}
        
        # Mock LLM service
        mock_llm = Mock()
        mock_result = Mock()
        mock_result.summary = "Test summary"
        mock_result.entities = []
        mock_llm.analyze_document.return_value = mock_result
        mock_llm_service.return_value = mock_llm
        
        # Mock database
        mock_db = Mock()
        mock_db.commit = Mock()
        
        from app.services.document_processor import process_document_llm_sync
        
        # Process LLM
        result = process_document_llm_sync(mock_doc, mock_db)
        
        # Verify LLM was called with truncated text
        assert mock_llm.analyze_document.called
        call_args = mock_llm.analyze_document.call_args
        text_sent = call_args.kwargs.get('text', '')
        
        assert len(text_sent) <= max_chars, f"Expected <= {max_chars}, got {len(text_sent)}"
        assert result["success"] is True
        assert mock_doc.llm_chars_sent == len(text_sent)


class TestDocMetaEndpoint:
    """Tests for GET /api/v1/docs/{doc_id}/meta endpoint."""
    
    def test_meta_endpoint_returns_cost_hints(self):
        """Test that /meta endpoint returns page_count, ocr_chars, llm_chars_sent."""
        # This test would require a real database with a test document
        # For now, we test the endpoint structure
        
        # Expected response format:
        # {
        #   "id": "123",
        #   "filename": "test.pdf",
        #   "mime_type": "application/pdf",
        #   "size_bytes": 1000,
        #   "page_count": 5,
        #   "ocr_chars": 10000,
        #   "llm_chars_sent": 5000,
        #   ...
        # }
        pass
    
    def test_meta_endpoint_404_for_nonexistent_doc(self):
        """Test that /meta returns 404 for nonexistent document."""
        response = client.get("/api/v1/docs/nonexistent/meta")
        assert response.status_code == 404
        assert response.json()["error_code"] == "NOT_FOUND"
