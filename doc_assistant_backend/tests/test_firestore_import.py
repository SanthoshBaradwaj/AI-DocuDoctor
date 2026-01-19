"""Test that importing app.main with DB_PROVIDER=firestore does not crash."""
import os
import pytest
from unittest.mock import patch


def test_import_main_with_firestore():
    """Test that importing app.main with DB_PROVIDER=firestore does not crash."""
    # Set environment to Firestore mode
    with patch.dict(os.environ, {
        "DB_PROVIDER": "firestore",
        "GOOGLE_PROJECT_ID": "test-project",
        "STORAGE_PROVIDER": "gcs",
        "GCS_BUCKET": "test-bucket",
        "TASK_QUEUE_PROVIDER": "http",
        "PUBLIC_BASE_URL": "https://test.example.com",
        # Don't set DATABASE_URL to simulate Firestore mode
    }):
        # Clear any cached settings
        from app.core.config import get_settings
        get_settings.cache_clear()
        
        # This should not crash - SQLAlchemy engine should not be created
        try:
            # Import main module - this should not create SQL engine
            import app.main
            assert True, "app.main imported successfully without crashing"
        except RuntimeError as e:
            # If we get a RuntimeError about DATABASE_URL, that's expected for SQL mode
            # But we're in Firestore mode, so this shouldn't happen
            if "DATABASE_URL" in str(e):
                pytest.fail(f"Unexpected RuntimeError about DATABASE_URL in Firestore mode: {e}")
            raise
        except Exception as e:
            # Any other exception is a failure
            pytest.fail(f"Importing app.main with Firestore mode crashed: {e}")


def test_sql_mode_requires_database_url():
    """Test that SQL mode raises RuntimeError if DATABASE_URL is not set."""
    with patch.dict(os.environ, {
        "DB_PROVIDER": "sql",
        # Don't set DATABASE_URL
    }):
        # Clear cached settings
        from app.core.config import get_settings
        get_settings.cache_clear()
        
        # Importing sql_alchemy should raise RuntimeError
        with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
            from app.infrastructure.db import sql_alchemy


def test_firestore_mode_does_not_create_engine():
    """Test that Firestore mode does not create SQLAlchemy engine."""
    with patch.dict(os.environ, {
        "DB_PROVIDER": "firestore",
        "GOOGLE_PROJECT_ID": "test-project",
    }):
        # Clear cached settings
        from app.core.config import get_settings
        get_settings.cache_clear()
        
        # Import sql_alchemy - engine should be None
        from app.infrastructure.db import sql_alchemy
        assert sql_alchemy.engine is None, "Engine should be None in Firestore mode"
        assert sql_alchemy.SessionLocal is None, "SessionLocal should be None in Firestore mode"
