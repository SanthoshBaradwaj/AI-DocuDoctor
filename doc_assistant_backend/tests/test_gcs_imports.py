"""Smoke test to verify Google Cloud Storage imports work."""
import pytest


def test_gcs_storage_imports():
    """Test that GCS storage module can be imported without errors."""
    try:
        from app.infrastructure.storage import gcs_storage
        assert gcs_storage is not None
    except ImportError as e:
        pytest.fail(f"Failed to import gcs_storage: {e}. Make sure google-cloud-storage is installed.")


def test_gcs_storage_functions_exist():
    """Test that GCS storage functions are available."""
    from app.infrastructure.storage import gcs_storage
    
    # Verify key functions exist
    assert hasattr(gcs_storage, 'get_gcs_bucket_name')
    assert hasattr(gcs_storage, 'make_gcs_client')
    assert hasattr(gcs_storage, 'presign_upload_v4')
    assert hasattr(gcs_storage, 'presign_download_v4')
    assert hasattr(gcs_storage, 'format_storage_key')


def test_firestore_adapter_imports():
    """Test that Firestore adapter module can be imported without errors."""
    try:
        from app.infrastructure.db import firestore_adapter
        assert firestore_adapter is not None
    except ImportError as e:
        pytest.fail(f"Failed to import firestore_adapter: {e}. Make sure google-cloud-firestore is installed.")


def test_firestore_adapter_classes_exist():
    """Test that Firestore adapter classes are available."""
    from app.infrastructure.db import firestore_adapter
    
    # Verify key classes exist
    assert hasattr(firestore_adapter, 'FirestoreDocumentAdapter')
    assert hasattr(firestore_adapter, 'FirestoreQuery')
    assert hasattr(firestore_adapter, 'get_firestore_db')
