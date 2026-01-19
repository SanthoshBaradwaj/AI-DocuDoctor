"""Helper functions for database-agnostic operations."""
from typing import Any, Optional
from app.infrastructure.db.models import Document
from app.core.logging import get_logger

logger = get_logger(__name__)


def get_document(db: Any, doc_id: Any) -> Optional[Document]:
    """Get a document by ID in a backend-agnostic way.
    
    Detects whether db is a Firestore adapter or SQLAlchemy session
    and calls the appropriate method.
    
    Args:
        db: Database session/adapter (SQLAlchemy Session or FirestoreDocumentAdapter)
        doc_id: Document ID (int for SQL, str for Firestore)
        
    Returns:
        Document instance or None if not found
    """
    # Check if it's a Firestore adapter by class name
    is_firestore = "Firestore" in db.__class__.__name__
    
    if is_firestore:
        # Firestore adapter: db.get(doc_id)
        return db.get(doc_id)
    else:
        # SQLAlchemy: db.get(Document, doc_id)
        # Try SQLAlchemy signature first
        try:
            return db.get(Document, doc_id)
        except TypeError:
            # If TypeError (wrong number of args), try Firestore signature
            logger.warning(
                "SQLAlchemy get() failed, trying Firestore signature",
                extra={
                    "db_type": db.__class__.__name__,
                    "doc_id": doc_id,
                }
            )
            return db.get(doc_id)


def is_firestore_adapter(db: Any) -> bool:
    """Check if db is a Firestore adapter.
    
    Args:
        db: Database session/adapter
        
    Returns:
        True if Firestore adapter, False if SQLAlchemy session
    """
    return "Firestore" in db.__class__.__name__


def update_document(db: Any, doc: Document) -> None:
    """Update a document in a backend-agnostic way.
    
    For Firestore, explicitly calls update_document() before commit.
    For SQLAlchemy, modifications are tracked automatically.
    
    Args:
        db: Database session/adapter
        doc: Document instance to update
    """
    is_firestore = is_firestore_adapter(db)
    
    if is_firestore:
        # Firestore adapter: explicitly call update_document()
        db.update_document(doc)
    else:
        # SQLAlchemy: modifications are tracked automatically, no explicit call needed
        # Just ensure the document is in the session (it should be if we got it via get())
        pass
