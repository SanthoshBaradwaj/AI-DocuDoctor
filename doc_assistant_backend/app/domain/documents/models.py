from datetime import datetime, date
from typing import Any, Dict, Optional
from pydantic import BaseModel
from .doc_types import DocumentDomain, DocumentType


class DocumentStatus(str):
    """Document processing status."""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


class Document(BaseModel):
    """Domain model for a document."""
    id: int
    user_id: int
    domain: Optional[DocumentDomain] = None
    doc_type: Optional[DocumentType] = None
    title: str
    storage_key: str
    mime_type: str
    size_bytes: int
    status: str
    created_at: datetime
    updated_at: datetime
    expiry_date: Optional[date] = None
    extracted: Optional[Dict[str, Any]] = None  # AI structured fields
    ocr_text_available: bool = False  # flag for later use
    
    class Config:
        from_attributes = True


# Domain service functions (placeholders for now)
def map_db_to_domain(db_doc) -> Document:
    """Map a database document model to a domain document model.
    
    Args:
        db_doc: SQLAlchemy Document model instance
        
    Returns:
        Domain Document model
    """
    return Document(
        id=db_doc.id,
        user_id=db_doc.owner_id,
        domain=DocumentDomain(db_doc.domain) if db_doc.domain else None,
        doc_type=DocumentType(db_doc.doc_type) if db_doc.doc_type else None,
        title=db_doc.title,
        storage_key=db_doc.s3_key,
        mime_type=db_doc.mime,
        size_bytes=db_doc.size,
        status=db_doc.status,
        created_at=db_doc.created_at if hasattr(db_doc, 'created_at') else datetime.now(),
        updated_at=db_doc.updated_at if hasattr(db_doc, 'updated_at') else datetime.now(),
        expiry_date=db_doc.expiry_date if hasattr(db_doc, 'expiry_date') else None,
        extracted=db_doc.extracted or {},
        ocr_text_available=bool(db_doc.body),
    )


def map_domain_to_db(doc: Document, db_doc=None):
    """Map a domain document model to a database document model.
    
    Args:
        doc: Domain Document model
        db_doc: Optional existing SQLAlchemy Document model instance to update
        
    Returns:
        SQLAlchemy Document model instance
    """
    # This will be implemented when we need to create/update documents
    # For now, just a placeholder
    if db_doc:
        db_doc.domain = doc.domain.value if doc.domain else None
        db_doc.doc_type = doc.doc_type.value if doc.doc_type else None
        db_doc.expiry_date = doc.expiry_date
        db_doc.extracted = doc.extracted
        return db_doc
    # Would create new instance here if needed
    raise NotImplementedError("Creating new DB documents from domain model not yet implemented")
