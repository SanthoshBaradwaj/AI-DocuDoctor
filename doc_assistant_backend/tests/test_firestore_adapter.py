"""Unit tests for Firestore adapter."""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, date

from app.infrastructure.db.firestore_adapter import (
    FirestoreDocumentAdapter,
    FirestoreQuery,
)
from app.infrastructure.db.models import Document
from app.core.constants import PipelineStepStatus


@pytest.fixture
def mock_firestore_client():
    """Mock Firestore client."""
    with patch('app.infrastructure.db.firestore_adapter.firestore.Client') as mock_client:
        client = Mock()
        collection = Mock()
        doc_ref = Mock()
        doc_snapshot = Mock()
        
        client.collection.return_value = collection
        collection.document.return_value = doc_ref
        doc_ref.get.return_value = doc_snapshot
        doc_ref.set.return_value = None
        doc_ref.delete.return_value = None
        
        mock_client.return_value = client
        yield client, collection, doc_ref, doc_snapshot


class TestFirestoreDocumentAdapter:
    """Tests for FirestoreDocumentAdapter."""
    
    @patch('app.infrastructure.db.firestore_adapter.get_settings')
    def test_get_document_exists(self, mock_settings, mock_firestore_client):
        """Test getting an existing document."""
        client, collection, doc_ref, doc_snapshot = mock_firestore_client
        mock_settings.return_value.GOOGLE_PROJECT_ID = "test-project"
        
        # Mock document snapshot
        doc_snapshot.exists = True
        doc_snapshot.id = "123"
        doc_snapshot.to_dict.return_value = {
            "owner_id": 1,
            "title": "Test Document",
            "filename": "test.pdf",
            "s3_key": "gs://bucket/path",
            "size": 1000,
            "mime": "application/pdf",
            "status": "ready",
            "ocr_status": PipelineStepStatus.READY.value,
            "llm_status": PipelineStepStatus.READY.value,
            "excerpt": "Test excerpt",
            "body": "Test body",
            "extracted": None,
            "domain": None,
            "doc_type": None,
            "request_id": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        
        adapter = FirestoreDocumentAdapter()
        doc = adapter.get("123")
        
        assert doc is not None
        assert doc.id == 123 or doc.id == "123"  # May be converted to int
        assert doc.title == "Test Document"
    
    @patch('app.infrastructure.db.firestore_adapter.get_settings')
    def test_get_document_not_found(self, mock_settings, mock_firestore_client):
        """Test getting a non-existent document."""
        client, collection, doc_ref, doc_snapshot = mock_firestore_client
        mock_settings.return_value.GOOGLE_PROJECT_ID = "test-project"
        
        doc_snapshot.exists = False
        
        adapter = FirestoreDocumentAdapter()
        doc = adapter.get("999")
        
        assert doc is None
    
    @patch('app.infrastructure.db.firestore_adapter.get_settings')
    def test_add_and_commit(self, mock_settings, mock_firestore_client):
        """Test adding and committing a document."""
        client, collection, doc_ref, doc_snapshot = mock_firestore_client
        mock_settings.return_value.GOOGLE_PROJECT_ID = "test-project"
        
        doc_ref.id = "new-doc-id"
        
        adapter = FirestoreDocumentAdapter()
        doc = Document()
        doc.owner_id = 1
        doc.title = "New Document"
        doc.filename = "new.pdf"
        doc.s3_key = "gs://bucket/new.pdf"
        doc.size = 2000
        doc.mime = "application/pdf"
        doc.status = "processing"
        doc.ocr_status = PipelineStepStatus.PENDING.value
        doc.llm_status = PipelineStepStatus.PENDING.value
        
        adapter.add(doc)
        adapter.commit()
        
        # Verify document was set
        doc_ref.set.assert_called_once()
        # Verify doc.id was updated
        assert doc.id == "new-doc-id"
