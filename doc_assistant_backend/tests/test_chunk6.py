"""Tests for EPIC1-CHUNK6: Observability, retries, enums, and provider metadata."""
import pytest
from unittest.mock import Mock, patch, MagicMock
import time
import httpx

from app.core.constants import PipelineStepStatus
from app.services.status import set_ocr_status, set_llm_status
from app.infrastructure.db.models import Document
from app.infrastructure.queue.celery_queue import process_document_ocr, process_document_llm
from app.infrastructure.ai.base import OcrResult, LlmResult


class TestPipelineStepStatus:
    """Tests for PipelineStepStatus enum."""
    
    def test_enum_values(self):
        """Test that enum values match expected strings."""
        assert PipelineStepStatus.PENDING.value == "pending"
        assert PipelineStepStatus.PROCESSING.value == "processing"
        assert PipelineStepStatus.READY.value == "ready"
        assert PipelineStepStatus.ERROR.value == "error"


class TestStatusHelpers:
    """Tests for status transition helpers."""
    
    def test_set_ocr_status_allowed_transitions(self):
        """Test that allowed OCR status transitions work."""
        doc = Mock(spec=Document)
        doc.id = 1
        doc.ocr_status = PipelineStepStatus.PENDING.value
        
        # Allowed: pending -> processing
        set_ocr_status(doc, PipelineStepStatus.PROCESSING)
        assert doc.ocr_status == PipelineStepStatus.PROCESSING.value
        
        # Allowed: processing -> ready
        doc.ocr_status = PipelineStepStatus.PROCESSING.value
        set_ocr_status(doc, PipelineStepStatus.READY)
        assert doc.ocr_status == PipelineStepStatus.READY.value
        
        # Allowed: ready -> pending (reprocessing)
        set_ocr_status(doc, PipelineStepStatus.PENDING, reason="reprocessing")
        assert doc.ocr_status == PipelineStepStatus.PENDING.value
    
    def test_set_llm_status_allowed_transitions(self):
        """Test that allowed LLM status transitions work."""
        doc = Mock(spec=Document)
        doc.id = 1
        doc.llm_status = PipelineStepStatus.PENDING.value
        
        # Allowed: pending -> processing
        set_llm_status(doc, PipelineStepStatus.PROCESSING)
        assert doc.llm_status == PipelineStepStatus.PROCESSING.value
        
        # Allowed: processing -> ready
        doc.llm_status = PipelineStepStatus.PROCESSING.value
        set_llm_status(doc, PipelineStepStatus.READY)
        assert doc.llm_status == PipelineStepStatus.READY.value


class TestProviderMetadata:
    """Tests for provider metadata in extracted field."""
    
    @patch('app.infrastructure.queue.celery_queue.get_ocr_service')
    @patch('app.infrastructure.queue.celery_queue.SessionLocal')
    @patch('app.infrastructure.queue.celery_queue.get_settings')
    def test_ocr_provider_metadata(self, mock_get_settings, mock_session_local, mock_get_ocr_service):
        """Test that OCR provider metadata is stored in extracted.ocr."""
        from app.core.config import Settings
        
        # Setup mock document
        mock_doc = Mock(spec=Document)
        mock_doc.id = 1
        mock_doc.status = "processing"
        mock_doc.ocr_status = PipelineStepStatus.PENDING.value
        mock_doc.s3_key = "test/key.pdf"
        mock_doc.mime = "application/pdf"
        mock_doc.domain = "IDENTITY"
        mock_doc.doc_type = "PASSPORT"
        mock_doc.body = ""
        mock_doc.excerpt = ""
        mock_doc.extracted = None
        mock_doc.request_id = None
        
        # Setup mock DB session
        mock_db = Mock()
        mock_db.get.return_value = mock_doc
        mock_session_local.return_value = mock_db
        
        # Setup mock settings
        mock_settings = Mock(spec=Settings)
        mock_settings.OCR_PROVIDER = "fake"
        mock_get_settings.return_value = mock_settings
        
        # Setup mock OCR service
        mock_ocr_service = Mock()
        mock_ocr_service.extract_document.return_value = OcrResult(
            text="Test text",
            page_count=1,
            language="en"
        )
        mock_get_ocr_service.return_value = mock_ocr_service
        
        # Mock Celery task request
        mock_self = Mock()
        mock_self.request.id = "test-task-id"
        mock_self.request.retries = 0
        mock_self.max_retries = 3
        
        # Execute task
        result = process_document_ocr(mock_self, 1)
        
        # Verify provider metadata was stored
        assert mock_doc.extracted is not None
        assert "ocr" in mock_doc.extracted
        assert mock_doc.extracted["ocr"]["provider"] == "fake"
        assert mock_doc.extracted["ocr"]["provider_name"] == "FakeOcrService"
        assert mock_doc.extracted["ocr"]["page_count"] == 1
        assert mock_doc.extracted["ocr"]["language"] == "en"
    
    @patch('app.infrastructure.queue.celery_queue.get_llm_service')
    @patch('app.infrastructure.queue.celery_queue.SessionLocal')
    @patch('app.infrastructure.queue.celery_queue.get_settings')
    def test_llm_provider_metadata(self, mock_get_settings, mock_session_local, mock_get_llm_service):
        """Test that LLM provider metadata is stored in extracted.llm."""
        from app.core.config import Settings
        
        # Setup mock document
        mock_doc = Mock(spec=Document)
        mock_doc.id = 1
        mock_doc.status = "ready"
        mock_doc.ocr_status = PipelineStepStatus.READY.value
        mock_doc.llm_status = PipelineStepStatus.PENDING.value
        mock_doc.body = "Test document text"
        mock_doc.mime = "text/plain"
        mock_doc.doc_type = "PASSPORT"
        mock_doc.domain = "IDENTITY"
        mock_doc.extracted = None
        mock_doc.request_id = None
        
        # Setup mock DB session
        mock_db = Mock()
        mock_db.get.return_value = mock_doc
        mock_session_local.return_value = mock_db
        
        # Setup mock settings
        mock_settings = Mock(spec=Settings)
        mock_settings.LLM_PROVIDER = "fake"
        mock_get_settings.return_value = mock_settings
        
        # Setup mock LLM service
        mock_llm_service = Mock()
        mock_llm_service.analyze_document.return_value = LlmResult(
            summary="Test summary",
            entities=[{"type": "TOKEN_COUNT", "value": 3}]
        )
        mock_get_llm_service.return_value = mock_llm_service
        
        # Mock Celery task request
        mock_self = Mock()
        mock_self.request.id = "test-task-id"
        mock_self.request.retries = 0
        mock_self.max_retries = 3
        
        # Execute task
        result = process_document_llm(mock_self, 1)
        
        # Verify provider metadata was stored
        assert mock_doc.extracted is not None
        assert "llm" in mock_doc.extracted
        assert mock_doc.extracted["llm"]["provider"] == "fake"
        assert mock_doc.extracted["llm"]["provider_name"] == "FakeLLMService"
        assert mock_doc.extracted["llm"]["summary"] == "Test summary"
        assert len(mock_doc.extracted["llm"]["entities"]) == 1
        
        # Verify backward compatibility (top-level fields)
        assert mock_doc.extracted["summary"] == "Test summary"
        assert mock_doc.extracted["entities"] == [{"type": "TOKEN_COUNT", "value": 3}]


class TestLifecycleEventLogs:
    """Tests for lifecycle event logs with timings."""
    
    @patch('app.infrastructure.queue.celery_queue.get_ocr_service')
    @patch('app.infrastructure.queue.celery_queue.SessionLocal')
    @patch('app.infrastructure.queue.celery_queue.get_settings')
    @patch('app.infrastructure.queue.celery_queue.get_logger')
    @patch('time.monotonic')
    def test_ocr_logs_include_event_and_timing(self, mock_monotonic, mock_get_logger, mock_get_settings, mock_session_local, mock_get_ocr_service):
        """Test that OCR logs include event type and duration."""
        from app.core.config import Settings
        
        # Setup time mock
        mock_monotonic.side_effect = [100.0, 100.5]  # 0.5 seconds
        
        # Setup mock logger
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        # Setup mock document
        mock_doc = Mock(spec=Document)
        mock_doc.id = 1
        mock_doc.status = "processing"
        mock_doc.ocr_status = PipelineStepStatus.PENDING.value
        mock_doc.s3_key = "test/key.pdf"
        mock_doc.mime = "application/pdf"
        mock_doc.domain = None
        mock_doc.doc_type = None
        mock_doc.body = ""
        mock_doc.excerpt = ""
        mock_doc.extracted = None
        mock_doc.request_id = None
        
        # Setup mock DB session
        mock_db = Mock()
        mock_db.get.return_value = mock_doc
        mock_session_local.return_value = mock_db
        
        # Setup mock settings
        mock_settings = Mock(spec=Settings)
        mock_settings.OCR_PROVIDER = "fake"
        mock_get_settings.return_value = mock_settings
        
        # Setup mock OCR service
        mock_ocr_service = Mock()
        mock_ocr_service.extract_document.return_value = OcrResult(
            text="Test text",
            page_count=1,
            language="en"
        )
        mock_get_ocr_service.return_value = mock_ocr_service
        
        # Mock Celery task request
        mock_self = Mock()
        mock_self.request.id = "test-task-id"
        mock_self.request.retries = 0
        mock_self.max_retries = 3
        
        # Execute task
        result = process_document_ocr(mock_self, 1)
        
        # Verify success log was called with event and duration
        success_calls = [call for call in mock_logger.info.call_args_list 
                        if len(call[0]) > 0 and "ocr.success" in str(call)]
        assert len(success_calls) > 0
        
        # Check that duration_ms is in the log
        call_kwargs = success_calls[0][1] if len(success_calls[0]) > 1 else {}
        extra = call_kwargs.get("extra", {})
        assert "event" in extra
        assert extra["event"] == "ocr.success"
        assert "duration_ms" in extra
        assert extra["duration_ms"] == 500.0  # 0.5 seconds * 1000


class TestRetryPolicy:
    """Tests for retry policy on transient errors."""
    
    @patch('app.infrastructure.queue.celery_queue.get_ocr_service')
    @patch('app.infrastructure.queue.celery_queue.SessionLocal')
    @patch('app.infrastructure.queue.celery_queue.get_settings')
    def test_transient_error_triggers_retry(self, mock_get_settings, mock_session_local, mock_get_ocr_service):
        """Test that transient errors (httpx.RequestError) trigger retry."""
        from app.core.config import Settings
        
        # Setup mock document
        mock_doc = Mock(spec=Document)
        mock_doc.id = 1
        mock_doc.status = "processing"
        mock_doc.ocr_status = PipelineStepStatus.PENDING.value
        mock_doc.s3_key = "test/key.pdf"
        mock_doc.mime = "application/pdf"
        mock_doc.domain = None
        mock_doc.doc_type = None
        mock_doc.request_id = None
        
        # Setup mock DB session
        mock_db = Mock()
        mock_db.get.return_value = mock_doc
        mock_session_local.return_value = mock_db
        
        # Setup mock settings
        mock_settings = Mock(spec=Settings)
        mock_settings.OCR_PROVIDER = "http"
        mock_get_settings.return_value = mock_settings
        
        # Setup mock OCR service to raise transient error
        mock_ocr_service = Mock()
        mock_ocr_service.extract_document.side_effect = httpx.RequestError("Network error")
        mock_get_ocr_service.return_value = mock_ocr_service
        
        # Mock Celery task request
        mock_self = Mock()
        mock_self.request.id = "test-task-id"
        mock_self.request.retries = 0
        mock_self.max_retries = 3
        
        # Execute task - should raise to trigger retry
        with pytest.raises(httpx.RequestError):
            process_document_ocr(mock_self, 1)
        
        # Verify status was NOT set to error (will retry)
        # Status should only be set to error after max retries
        assert mock_doc.ocr_status != PipelineStepStatus.ERROR.value
    
    @patch('app.infrastructure.queue.celery_queue.get_ocr_service')
    @patch('app.infrastructure.queue.celery_queue.SessionLocal')
    @patch('app.infrastructure.queue.celery_queue.get_settings')
    def test_non_transient_error_no_retry(self, mock_get_settings, mock_session_local, mock_get_ocr_service):
        """Test that non-transient errors do not trigger retry."""
        from app.core.config import Settings
        
        # Setup mock document
        mock_doc = Mock(spec=Document)
        mock_doc.id = 1
        mock_doc.status = "processing"
        mock_doc.ocr_status = PipelineStepStatus.PENDING.value
        mock_doc.s3_key = "test/key.pdf"
        mock_doc.mime = "application/pdf"
        mock_doc.domain = None
        mock_doc.doc_type = None
        mock_doc.request_id = None
        
        # Setup mock DB session
        mock_db = Mock()
        mock_db.get.return_value = mock_doc
        mock_session_local.return_value = mock_db
        
        # Setup mock settings
        mock_settings = Mock(spec=Settings)
        mock_settings.OCR_PROVIDER = "fake"
        mock_get_settings.return_value = mock_settings
        
        # Setup mock OCR service to raise non-transient error
        mock_ocr_service = Mock()
        mock_ocr_service.extract_document.side_effect = ValueError("Invalid format")
        mock_get_ocr_service.return_value = mock_ocr_service
        
        # Mock Celery task request
        mock_self = Mock()
        mock_self.request.id = "test-task-id"
        mock_self.request.retries = 0
        mock_self.max_retries = 3
        
        # Execute task - should NOT raise (non-transient error)
        result = process_document_ocr(mock_self, 1)
        
        # Verify status was set to error
        assert "error" in result
        # Status should be set to error for non-transient errors
        assert mock_doc.ocr_status == PipelineStepStatus.ERROR.value

