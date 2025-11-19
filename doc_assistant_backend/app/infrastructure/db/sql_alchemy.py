from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from datetime import datetime

from app.core.config import get_settings
from app.domain.documents.models import Document as DomainDocument, map_db_to_domain
from app.domain.documents.doc_types import DocumentDomain, DocumentType

settings = get_settings()

engine = create_engine(str(settings.DATABASE_URL), echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_extensions():
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
