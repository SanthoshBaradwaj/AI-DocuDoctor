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
    
    Uses robust detection: class name contains "Firestore" OR has methods
    that indicate Firestore adapter (e.g., _doc_to_dict, _dict_to_doc).
    
    Args:
        db: Database session/adapter
        
    Returns:
        True if Firestore adapter, False if SQLAlchemy session
    """
    # Check class name
    if "Firestore" in db.__class__.__name__:
        return True
    
    # Check for Firestore-specific methods
    if hasattr(db, "_doc_to_dict") and hasattr(db, "_dict_to_doc"):
        return True
    
    return False


def update_document(db: Any, doc: Document) -> None:
    """Update a document in a backend-agnostic way.
    
    For Firestore, explicitly calls update_document() before commit.
    For SQLAlchemy, modifications are tracked automatically.
    
    Args:
        db: Database session/adapter
        doc: Document instance to update
        
    Raises:
        ValueError: If Firestore adapter but document lacks ID
    """
    is_firestore = is_firestore_adapter(db)
    
    if is_firestore:
        # Firestore adapter: explicitly call update_document()
        # Safe fallback: if method doesn't exist, log warning but don't raise
        if hasattr(db, "update_document"):
            try:
                db.update_document(doc)
            except (ValueError, AttributeError) as e:
                logger.warning(
                    "Failed to call update_document on Firestore adapter",
                    extra={
                        "error": str(e),
                        "doc_id": getattr(doc, "id", None),
                    }
                )
                # Re-raise ValueError (document lacks ID) but not AttributeError
                if isinstance(e, ValueError):
                    raise
        else:
            logger.warning(
                "Firestore adapter lacks update_document method",
                extra={"db_class": db.__class__.__name__}
            )
    else:
        # SQLAlchemy: modifications are tracked automatically, no explicit call needed
        pass
