"""Database factory for selecting SQL or Firestore provider."""
from typing import Union
from app.core.config import get_settings

settings = get_settings()


def get_db():
    """Get database session/adapter based on DB_PROVIDER setting.
    
    This is a FastAPI dependency generator that yields the appropriate database
    session or adapter based on configuration.
    
    Yields:
        SQLAlchemy session (for SQL mode) or FirestoreDocumentAdapter (for Firestore mode)
    """
    provider = settings.DB_PROVIDER or "sql"
    
    if provider == "firestore":
        # Lazy import to avoid SQLAlchemy engine creation
        from app.infrastructure.db.firestore_adapter import FirestoreDocumentAdapter
        adapter = FirestoreDocumentAdapter()
        # Firestore adapter doesn't need cleanup, just yield it
        yield adapter
    else:
        # Lazy import to avoid engine creation when using Firestore
        from app.infrastructure.db.sql_alchemy import get_db as get_sql_db
        # get_sql_db is already a generator, yield from it directly
        yield from get_sql_db()


def get_session_local():
    """Get session local factory (for SQL only).
    
    Returns:
        SessionLocal for SQL, None for Firestore
        
    Raises:
        RuntimeError: If DB_PROVIDER is not 'sql'
    """
    provider = settings.DB_PROVIDER or "sql"
    
    if provider == "firestore":
        return None  # Firestore doesn't use session local
    else:
        # Lazy import to avoid engine creation when using Firestore
        from app.infrastructure.db.sql_alchemy import SessionLocal as SQLSessionLocal
        if SQLSessionLocal is None:
            raise RuntimeError("SessionLocal not available: DB_PROVIDER is not 'sql' or DATABASE_URL is not set")
        return SQLSessionLocal
