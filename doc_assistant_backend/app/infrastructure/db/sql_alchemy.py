from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from datetime import datetime

from app.core.config import get_settings
from app.domain.documents.models import Document as DomainDocument, map_db_to_domain
from app.domain.documents.doc_types import DocumentDomain, DocumentType

settings = get_settings()

# Guard engine creation: only create if DATABASE_URL is set and DB_PROVIDER is sql
# This prevents crashes when DB_PROVIDER=firestore (where DATABASE_URL is None)
_db_provider = getattr(settings, "DB_PROVIDER", None) or "sql"
_has_database_url = bool(settings.DATABASE_URL)

if _db_provider == "sql":
    if not _has_database_url:
        raise RuntimeError(
            "DATABASE_URL is required when DB_PROVIDER=sql. "
            "Set DATABASE_URL environment variable or use DB_PROVIDER=firestore."
        )
    engine = create_engine(str(settings.DATABASE_URL), echo=False, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
else:
    # Firestore mode: engine and SessionLocal are not used
    engine = None
    SessionLocal = None

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_extensions():
    """Create database extensions (PostgreSQL only)."""
    if engine is None:
        raise RuntimeError("Cannot create extensions: SQL engine not initialized (DB_PROVIDER is not 'sql')")
    with engine.connect() as conn:
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception:
            pass


# Mapping helpers for DB ↔ Domain
def db_document_to_domain(db_doc) -> DomainDocument:
    """Convert a SQLAlchemy Document model to a domain Document model.
    
    Args:
        db_doc: SQLAlchemy Document model instance
        
    Returns:
        Domain Document model
    """
    return map_db_to_domain(db_doc)
