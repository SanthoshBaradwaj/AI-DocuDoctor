"""Tests for Firestore document persistence."""
import pytest
from unittest.mock import Mock, MagicMock, patch
from app.infrastructure.db.firestore_adapter import FirestoreDocumentAdapter
from app.infrastructure.db.models import Document
from app.core.constants import PipelineStepStatus


def test_firestore_adapter_update_document():
    """Test that update_document() persists changes to Firestore."""
    # Mock Firestore client
    mock_firestore_client = Mock()
    mock_doc_ref = Mock()
    mock_firestore_client.collection.return_value.document.return_value = mock_doc_ref
    
    # Create adapter
    with patch('app.infrastructure.db.firestore_adapter.firestore.Client', return_value=mock_firestore_client):
        adapter = FirestoreDocumentAdapter()
        adapter.db = mock_firestore_client
    
    # Create a document with an ID
    doc = Document()
    doc.id = "test_doc_123"
    doc.body = "Test content"
    doc.ocr_status = PipelineStepStatus.READY.value
    doc.status = "ready"
    doc.extracted = {"ocr": {"page_count": 1}}
    
    # Call update_document and commit
    adapter.update_document(doc)
    adapter.commit()
    
    # Verify that set() was called on the document reference
    mock_firestore_client.collection.assert_called_with("documents")
    mock_firestore_client.collection.return_value.document.assert_called_with("test_doc_123")
    mock_doc_ref.set.assert_called_once()
    
    # Verify the data passed to set() includes our changes
    call_args = mock_doc_ref.set.call_args
    assert call_args is not None
    data = call_args[0][0]  # First positional argument
    assert data["body"] == "Test content"
    assert data["ocr_status"] == PipelineStepStatus.READY.value
    assert data["status"] == "ready"
    assert data["extracted"]["ocr"]["page_count"] == 1


def test_firestore_adapter_get_returns_updated_values():
    """Test that after updating a document, get() returns the updated values."""
    # Mock Firestore client and document snapshot
    mock_firestore_client = Mock()
    mock_doc_ref = Mock()
    mock_snapshot = Mock()
    
    # Setup: document exists with initial values
    initial_data = {
        "body": "",
        "ocr_status": PipelineStepStatus.PENDING.value,
        "status": "uploaded",
        "extracted": {},
    }
    mock_snapshot.exists = True
    mock_snapshot.id = "test_doc_123"
    mock_snapshot.to_dict.return_value = initial_data
    mock_doc_ref.get.return_value = mock_snapshot
    mock_firestore_client.collection.return_value.document.return_value = mock_doc_ref
    
    # Create adapter
    with patch('app.infrastructure.db.firestore_adapter.firestore.Client', return_value=mock_firestore_client):
        adapter = FirestoreDocumentAdapter()
        adapter.db = mock_firestore_client
    
    # Get document
    doc = adapter.get("test_doc_123")
    assert doc is not None
    assert doc.body == ""
    assert doc.ocr_status == PipelineStepStatus.PENDING.value
    
    # Update document
    doc.body = "Updated content"
    doc.ocr_status = PipelineStepStatus.READY.value
    doc.status = "ready"
    doc.extracted = {"ocr": {"page_count": 1}}
    
    adapter.update_document(doc)
    adapter.commit()
    
    # Simulate Firestore returning updated data
    updated_data = {
        "body": "Updated content",
        "ocr_status": PipelineStepStatus.READY.value,
        "status": "ready",
        "extracted": {"ocr": {"page_count": 1}},
    }
    mock_snapshot.to_dict.return_value = updated_data
    
    # Get document again - should return updated values
    updated_doc = adapter.get("test_doc_123")
    assert updated_doc.body == "Updated content"
    assert updated_doc.ocr_status == PipelineStepStatus.READY.value
    assert updated_doc.status == "ready"


def test_llm_readiness_with_body():
    """Test that LLM processor proceeds when doc.body is set."""
    from app.services.document_processor import process_document_llm_sync
    from unittest.mock import Mock
    
    # Create a document with body
    doc = Document()
    doc.id = "test_doc"
    doc.body = "Test content for LLM"
    doc.status = "ready"
    doc.ocr_status = PipelineStepStatus.READY.value
    doc.extracted = {}
    
    # Mock database
    db = Mock()
    db.__class__.__name__ = "Session"  # SQLAlchemy session
    
    # Mock LLM service
    from app.infrastructure.ai.base import LlmResult
    mock_llm_service = Mock()
    mock_llm_service.analyze_document.return_value = LlmResult(
        summary="Test summary",
        entities=[{"type": "TOKEN_COUNT", "value": "3"}]
    )
    
    with patch('app.services.document_processor.get_llm_service', return_value=mock_llm_service):
        with patch('app.services.document_processor.update_document'):
            result = process_document_llm_sync(doc, db)
    
    # Should succeed (not return error about not ready)
    assert result.get("success") is True
    assert "error" not in result or not result.get("error")


def test_llm_readiness_with_extracted_text():
    """Test that LLM processor proceeds when extracted.get('text') is set."""
    from app.services.document_processor import process_document_llm_sync
    from unittest.mock import Mock
    
    # Create a document with text in extracted field
    doc = Document()
    doc.id = "test_doc"
    doc.body = ""  # Empty body
    doc.status = "ready"
    doc.ocr_status = PipelineStepStatus.READY.value
    doc.extracted = {"text": "Text from extracted field"}
    
    # Mock database
    db = Mock()
    db.__class__.__name__ = "Session"  # SQLAlchemy session
    
    # Mock LLM service
    from app.infrastructure.ai.base import LlmResult
    mock_llm_service = Mock()
    mock_llm_service.analyze_document.return_value = LlmResult(
        summary="Test summary",
        entities=[{"type": "TOKEN_COUNT", "value": "5"}]
    )
    
    with patch('app.services.document_processor.get_llm_service', return_value=mock_llm_service):
        with patch('app.services.document_processor.update_document'):
            result = process_document_llm_sync(doc, db)
    
    # Should succeed and use extracted text
    assert result.get("success") is True
    assert doc.body == "Text from extracted field"  # Should be copied to body
