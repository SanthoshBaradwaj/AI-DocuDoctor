"""Quick unit test validating Firestore adapter persists updates."""
import pytest
from unittest.mock import Mock, patch
from app.infrastructure.db.firestore_adapter import FirestoreDocumentAdapter
from app.infrastructure.db.models import Document
from app.core.constants import PipelineStepStatus


def test_firestore_adapter_persists_updates():
    """Test that Firestore adapter persists document updates correctly.
    
    Steps:
    1. Create doc, commit (add)
    2. Modify body/status, call update_document+commit
    3. Fetch again and assert values changed
    """
    # Mock Firestore client
    mock_firestore_client = Mock()
    mock_collection = Mock()
    mock_doc_ref = Mock()
    mock_snapshot = Mock()
    
    # Setup collection and document references
    mock_firestore_client.collection.return_value = mock_collection
    mock_collection.document.return_value = mock_doc_ref
    mock_doc_ref.get.return_value = mock_snapshot
    mock_doc_ref.id = "test_doc_123"
    
    # Initial document data (after first add)
    initial_data = {
        "owner_id": 1,
        "title": "Test Document",
        "filename": "test.txt",
        "s3_key": "test/path",
        "size": 100,
        "mime": "text/plain",
        "status": "uploaded",
        "ocr_status": PipelineStepStatus.PENDING.value,
        "llm_status": PipelineStepStatus.PENDING.value,
        "excerpt": "",
        "body": "",
        "extracted": {},
        "domain": None,
        "doc_type": None,
        "request_id": None,
    }
    mock_snapshot.exists = True
    mock_snapshot.id = "test_doc_123"
    mock_snapshot.to_dict.return_value = initial_data
    
    # Create adapter
    with patch('app.infrastructure.db.firestore_adapter.firestore.Client', return_value=mock_firestore_client):
        adapter = FirestoreDocumentAdapter()
        adapter.db = mock_firestore_client
    
    # Step 1: Create doc, commit (add)
    doc = Document()
    doc.id = "test_doc_123"
    doc.owner_id = 1
    doc.title = "Test Document"
    doc.filename = "test.txt"
    doc.s3_key = "test/path"
    doc.size = 100
    doc.mime = "text/plain"
    doc.status = "uploaded"
    doc.ocr_status = PipelineStepStatus.PENDING.value
    doc.body = ""
    doc.extracted = {}
    
    adapter.add(doc)
    adapter.commit()
    
    # Verify add was called
    assert mock_doc_ref.set.call_count == 1
    add_call_data = mock_doc_ref.set.call_args[0][0]
    assert add_call_data["body"] == ""
    assert add_call_data["ocr_status"] == PipelineStepStatus.PENDING.value
    
    # Step 2: Modify body/status, call update_document+commit
    doc.body = "Updated content from OCR"
    doc.ocr_status = PipelineStepStatus.READY.value
    doc.status = "ready"
    doc.extracted = {
        "text": "Updated content from OCR",
        "ocr": {"page_count": 1, "language": "en"}
    }
    
    adapter.update_document(doc)
    adapter.commit()
    
    # Verify update was called
    assert mock_doc_ref.set.call_count == 2
    update_call = mock_doc_ref.set.call_args
    assert update_call is not None
    update_call_data = update_call[0][0]
    assert update_call[1]["merge"] is False  # Full overwrite
    
    # Verify updated values
    assert update_call_data["body"] == "Updated content from OCR"
    assert update_call_data["ocr_status"] == PipelineStepStatus.READY.value
    assert update_call_data["status"] == "ready"
    assert update_call_data["extracted"]["text"] == "Updated content from OCR"
    assert update_call_data["extracted"]["ocr"]["page_count"] == 1
    
    # Step 3: Simulate fetching again - update mock to return new data
    updated_data = {
        "owner_id": 1,
        "title": "Test Document",
        "filename": "test.txt",
        "s3_key": "test/path",
        "size": 100,
        "mime": "text/plain",
        "status": "ready",
        "ocr_status": PipelineStepStatus.READY.value,
        "llm_status": PipelineStepStatus.PENDING.value,
        "excerpt": "Updated content from OCR",
        "body": "Updated content from OCR",
        "extracted": {
            "text": "Updated content from OCR",
            "ocr": {"page_count": 1, "language": "en"}
        },
        "domain": None,
        "doc_type": None,
        "request_id": None,
    }
    mock_snapshot.to_dict.return_value = updated_data
    
    # Fetch again
    fetched_doc = adapter.get("test_doc_123")
    
    # Assert values changed
    assert fetched_doc is not None
    assert fetched_doc.body == "Updated content from OCR"
    assert fetched_doc.ocr_status == PipelineStepStatus.READY.value
    assert fetched_doc.status == "ready"
    assert fetched_doc.extracted["text"] == "Updated content from OCR"
    assert fetched_doc.extracted["ocr"]["page_count"] == 1
    
    # Verify doc.id stays as string
    assert isinstance(fetched_doc.id, str)
    assert fetched_doc.id == "test_doc_123"
