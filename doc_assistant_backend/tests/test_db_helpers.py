"""Smoke tests for database helper functions."""
import pytest
from unittest.mock import Mock, MagicMock
from app.infrastructure.db.db_helpers import get_document, is_firestore_adapter
from app.infrastructure.db.models import Document


def test_is_firestore_adapter_detection():
    """Test Firestore adapter detection."""
    # Mock Firestore adapter
    firestore_adapter = Mock()
    firestore_adapter.__class__.__name__ = "FirestoreDocumentAdapter"
    
    assert is_firestore_adapter(firestore_adapter) is True
    
    # Mock SQLAlchemy session
    sql_session = Mock()
    sql_session.__class__.__name__ = "Session"
    
    assert is_firestore_adapter(sql_session) is False


def test_get_document_firestore():
    """Test get_document with Firestore adapter."""
    # Mock Firestore adapter
    firestore_adapter = Mock()
    firestore_adapter.__class__.__name__ = "FirestoreDocumentAdapter"
    
    # Mock document
    mock_doc = Document()
    mock_doc.id = "test_doc_id"
    
    # Firestore adapter uses single-arg get()
    firestore_adapter.get.return_value = mock_doc
    
    result = get_document(firestore_adapter, "test_doc_id")
    
    assert result == mock_doc
    firestore_adapter.get.assert_called_once_with("test_doc_id")


def test_get_document_sqlalchemy():
    """Test get_document with SQLAlchemy session."""
    # Mock SQLAlchemy session
    sql_session = Mock()
    sql_session.__class__.__name__ = "Session"
    
    # Mock document
    mock_doc = Document()
    mock_doc.id = 123
    
    # SQLAlchemy uses two-arg get(Document, doc_id)
    sql_session.get.return_value = mock_doc
    
    result = get_document(sql_session, 123)
    
    assert result == mock_doc
    sql_session.get.assert_called_once_with(Document, 123)


def test_get_document_sqlalchemy_fallback():
    """Test get_document fallback when SQLAlchemy signature fails."""
    # Mock SQLAlchemy session that raises TypeError
    sql_session = Mock()
    sql_session.__class__.__name__ = "Session"
    
    # First call raises TypeError, second call succeeds
    mock_doc = Document()
    mock_doc.id = "test_doc_id"
    
    sql_session.get.side_effect = [
        TypeError("get() takes 2 positional arguments but 3 were given"),
        mock_doc
    ]
    
    result = get_document(sql_session, "test_doc_id")
    
    assert result == mock_doc
    # Should have tried SQLAlchemy signature first, then Firestore signature
    assert sql_session.get.call_count == 2
    sql_session.get.assert_any_call(Document, "test_doc_id")
    sql_session.get.assert_any_call("test_doc_id")
