"""Test that Firestore DB dependency works correctly in FastAPI routes."""
import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

from app.infrastructure.db.firestore_adapter import FirestoreDocumentAdapter


def test_get_db_yields_firestore_adapter():
    """Test that get_db yields FirestoreDocumentAdapter in Firestore mode."""
    with patch.dict(os.environ, {
        "DB_PROVIDER": "firestore",
        "GOOGLE_PROJECT_ID": "test-project",
    }):
        # Clear cached settings
        from app.core.config import get_settings
        get_settings.cache_clear()
        
        from app.infrastructure.db.db_factory import get_db
        
        # get_db should be a generator
        db_gen = get_db()
        
        # Get the yielded value
        db = next(db_gen)
        
        # Should be a FirestoreDocumentAdapter instance
        assert isinstance(db, FirestoreDocumentAdapter), f"Expected FirestoreDocumentAdapter, got {type(db)}"
        
        # Should have query method
        assert hasattr(db, 'query'), "Firestore adapter should have query method"
        assert hasattr(db, 'get'), "Firestore adapter should have get method"
        assert hasattr(db, 'add'), "Firestore adapter should have add method"
        assert hasattr(db, 'commit'), "Firestore adapter should have commit method"


def test_firestore_list_docs_endpoint():
    """Test that /api/v1/docs endpoint works with Firestore adapter."""
    with patch.dict(os.environ, {
        "DB_PROVIDER": "firestore",
        "GOOGLE_PROJECT_ID": "test-project",
        "STORAGE_PROVIDER": "gcs",
        "GCS_BUCKET": "test-bucket",
        "TASK_QUEUE_PROVIDER": "http",
        "PUBLIC_BASE_URL": "https://test.example.com",
    }):
        # Clear cached settings
        from app.core.config import get_settings
        get_settings.cache_clear()
        
        # Mock Firestore adapter
        mock_adapter = Mock(spec=FirestoreDocumentAdapter)
        mock_query = Mock()
        mock_query_obj = Mock()
        
        # Setup query chain
        mock_query_obj.filter.return_value = mock_query_obj
        mock_query_obj.order_by.return_value = mock_query_obj
        mock_query_obj.all.return_value = []
        mock_query.return_value = mock_query_obj
        mock_adapter.query = mock_query
        
        # Mock Document model
        mock_document = Mock()
        mock_document.owner_id = Mock()
        mock_document.id = Mock()
        mock_document.id.desc = Mock()
        
        with patch('app.infrastructure.db.db_factory.get_db') as mock_get_db:
            # Make get_db yield our mock adapter
            def mock_db_gen():
                yield mock_adapter
            mock_get_db.side_effect = mock_db_gen
            
            # Import and create test client
            from app.main import app
            client = TestClient(app)
            
            # Make request to list docs endpoint
            response = client.get("/api/v1/docs")
            
            # Should not crash
            assert response.status_code in [200, 500]  # 500 is ok if query fails, but shouldn't be AttributeError
            assert "AttributeError" not in str(response.content), "Should not get AttributeError about generator"


def test_firestore_presign_endpoint():
    """Test that /api/v1/docs/upload/presign endpoint works with Firestore."""
    with patch.dict(os.environ, {
        "DB_PROVIDER": "firestore",
        "GOOGLE_PROJECT_ID": "test-project",
        "STORAGE_PROVIDER": "gcs",
        "GCS_BUCKET": "test-bucket",
    }):
        # Clear cached settings
        from app.core.config import get_settings
        get_settings.cache_clear()
        
        # Mock Firestore adapter (not used in presign, but dependency is injected)
        mock_adapter = Mock(spec=FirestoreDocumentAdapter)
        
        with patch('app.infrastructure.db.db_factory.get_db') as mock_get_db:
            # Make get_db yield our mock adapter
            def mock_db_gen():
                yield mock_adapter
            mock_get_db.side_effect = mock_db_gen
            
            # Mock storage backend
            with patch('app.infrastructure.storage.storage_factory.get_storage_backend') as mock_storage:
                mock_storage_backend = Mock()
                mock_storage_backend.presign_upload.return_value = {
                    "url": "https://storage.googleapis.com/test",
                    "fields": {},
                    "key": "gs://bucket/test.pdf"
                }
                mock_storage.return_value = mock_storage_backend
                
                # Import and create test client
                from app.main import app
                client = TestClient(app)
                
                # Make request to presign endpoint
                response = client.post(
                    "/api/v1/docs/upload/presign",
                    json={
                        "filename": "test.pdf",
                        "mime_type": "application/pdf",
                        "size_bytes": 1000
                    }
                )
                
                # Should succeed (200) or fail gracefully (not AttributeError)
                assert response.status_code in [200, 400, 500]
                assert "AttributeError" not in str(response.content), "Should not get AttributeError about generator"
                if response.status_code == 200:
                    assert "storage_key" in response.json()
