"""Firestore database adapter for Document persistence."""
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timezone
from google.cloud import firestore
from google.cloud.firestore_v1 import SERVER_TIMESTAMP
from google.cloud.firestore_v1.base_query import BaseQuery

from app.core.config import get_settings
from app.core.constants import PipelineStepStatus
from app.infrastructure.db.models import Document

settings = get_settings()


def _coerce_datetime(value):
    """Safely convert Firestore timestamp to datetime.datetime.
    
    Handles various Firestore timestamp types including DatetimeWithNanoseconds
    which may or may not have a to_datetime() method.
    
    Args:
        value: Firestore timestamp value (can be None, datetime, DatetimeWithNanoseconds, etc.)
        
    Returns:
        datetime.datetime object (timezone-aware in UTC) or None if value is None
    """
    if value is None:
        return None

    # Firestore returns DatetimeWithNanoseconds which is often a datetime subclass
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    if hasattr(value, "to_datetime"):
        dt = value.to_datetime()
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    if hasattr(value, "timestamp"):
        return datetime.fromtimestamp(value.timestamp(), tz=timezone.utc)

    return None


class FirestoreDocumentAdapter:
    """Adapter that provides SQLAlchemy-like interface for Firestore Document operations."""
    
    def __init__(self):
        self.db = firestore.Client(project=settings.GOOGLE_PROJECT_ID)
        self.collection = "documents"
    
    def _doc_to_dict(self, doc: Document) -> Dict[str, Any]:
        """Convert SQLAlchemy Document model to Firestore dict."""
        data = {
            "owner_id": doc.owner_id,
            "title": doc.title,
            "filename": doc.filename,
            "s3_key": doc.s3_key,
            "size": doc.size,
            "mime": doc.mime,
            "status": doc.status,
            "ocr_status": doc.ocr_status,
            "llm_status": doc.llm_status,
            "excerpt": doc.excerpt or "",
            "body": doc.body or "",
            "extracted": doc.extracted,
            "domain": doc.domain,
            "doc_type": doc.doc_type,
            "request_id": doc.request_id,
        }
        
        # Handle dates
        if doc.expiry_date:
            data["expiry_date"] = doc.expiry_date.isoformat()
        
        # Timestamps (use server timestamp for created_at/updated_at)
        if hasattr(doc, "created_at") and doc.created_at:
            data["created_at"] = doc.created_at
        else:
            data["created_at"] = SERVER_TIMESTAMP
        
        data["updated_at"] = SERVER_TIMESTAMP
        
        return data
    
    def _dict_to_doc(self, doc_id: str, data: Dict[str, Any]) -> Document:
        """Convert Firestore dict to SQLAlchemy-like Document model."""
        # Convert Firestore timestamp to datetime using safe helper
        created_at = _coerce_datetime(data.get("created_at"))
        if created_at is None:
            created_at = datetime.now(timezone.utc)
        
        updated_at = _coerce_datetime(data.get("updated_at"))
        if updated_at is None:
            updated_at = datetime.now(timezone.utc)
        
        # Convert expiry_date string to date if present
        expiry_date = None
        if data.get("expiry_date"):
            if isinstance(data["expiry_date"], str):
                expiry_date = date.fromisoformat(data["expiry_date"])
            elif isinstance(data["expiry_date"], date):
                expiry_date = data["expiry_date"]
        
        # Create Document instance (mimicking SQLAlchemy model)
        doc = Document()
        # Keep ID as string for Firestore (Pydantic schema will handle serialization)
        # Note: Document model has id: int for SQL compatibility, but Firestore uses string IDs
        doc.id = doc_id  # Keep as string for Firestore compatibility
        doc.owner_id = data.get("owner_id", 1)
        doc.title = data.get("title", "")
        doc.filename = data.get("filename", "")
        doc.s3_key = data.get("s3_key", "")
        doc.size = data.get("size", 0)
        doc.mime = data.get("mime", "application/octet-stream")
        doc.status = data.get("status", "uploaded")
        doc.ocr_status = data.get("ocr_status", PipelineStepStatus.PENDING.value)
        doc.llm_status = data.get("llm_status", PipelineStepStatus.PENDING.value)
        doc.excerpt = data.get("excerpt", "")
        doc.body = data.get("body", "")
        doc.extracted = data.get("extracted")
        doc.domain = data.get("domain")
        doc.doc_type = data.get("doc_type")
        doc.request_id = data.get("request_id")
        doc.expiry_date = expiry_date
        doc.created_at = created_at
        doc.updated_at = updated_at
        
        return doc
    
    def get(self, doc_id: Any) -> Optional[Document]:
        """Get document by ID (compatible with SQLAlchemy db.get).
        
        Args:
            doc_id: Document ID (int or string)
            
        Returns:
            Document instance or None if not found
        """
        doc_ref = self.db.collection(self.collection).document(str(doc_id))
        doc_snapshot = doc_ref.get()
        
        if not doc_snapshot.exists:
            return None
        
        data = doc_snapshot.to_dict()
        return self._dict_to_doc(doc_snapshot.id, data)
    
    def query(self, model_class):
        """Create a query object (compatible with SQLAlchemy db.query).
        
        Args:
            model_class: Model class (Document)
            
        Returns:
            FirestoreQuery object
        """
        return FirestoreQuery(self.db.collection(self.collection), model_class)
    
    def add(self, doc: Document) -> None:
        """Add document to Firestore (compatible with SQLAlchemy db.add).
        
        Note: This doesn't actually save - call commit() to save.
        
        Args:
            doc: Document instance
        """
        # Store document in instance for commit
        if not hasattr(self, "_pending_docs"):
            self._pending_docs = []
        self._pending_docs.append(("add", doc))
    
    def update_document(self, doc: Document) -> None:
        """Update an existing document in Firestore.
        
        This method explicitly updates a document that already exists.
        Call commit() to persist the changes.
        
        Args:
            doc: Document instance with an existing ID
        """
        if not hasattr(doc, "id") or not doc.id:
            raise ValueError("Document must have an ID to update")
        
        # Store document in instance for commit
        if not hasattr(self, "_pending_docs"):
            self._pending_docs = []
        self._pending_docs.append(("update", doc))
    
    def commit(self) -> None:
        """Commit pending operations (compatible with SQLAlchemy db.commit).
        
        Handles both new documents (via add()) and updates to existing documents.
        Persists all modified fields by replacing the entire document (merge=False).
        """
        if not hasattr(self, "_pending_docs") or not self._pending_docs:
            return
        
        for op, doc in self._pending_docs:
            data = self._doc_to_dict(doc)
            
            if op == "add":
                # If doc has an ID, use it; otherwise Firestore will auto-generate
                if hasattr(doc, "id") and doc.id:
                    doc_ref = self.db.collection(self.collection).document(str(doc.id))
                    doc_ref.set(data, merge=False)  # Full overwrite
                    # Ensure doc.id stays as string Firestore document id
                    doc.id = str(doc_ref.id)
                else:
                    # Auto-generate ID
                    doc_ref = self.db.collection(self.collection).document()
                    doc_ref.set(data, merge=False)  # Full overwrite
                    doc.id = str(doc_ref.id)
            elif op == "update":
                # Update existing document
                if not hasattr(doc, "id") or not doc.id:
                    raise ValueError("Cannot update document without ID")
                doc_ref = self.db.collection(self.collection).document(str(doc.id))
                # Use set() with merge=False to replace entire document, ensuring all fields persisted
                doc_ref.set(data, merge=False)
                # Ensure doc.id stays as string Firestore document id
                doc.id = str(doc_ref.id)
        
        # Clear pending operations
        self._pending_docs = []
    
    def refresh(self, doc: Document) -> None:
        """Refresh document from Firestore (compatible with SQLAlchemy db.refresh).
        
        Args:
            doc: Document instance to refresh
        """
        if not hasattr(doc, "id") or not doc.id:
            return
        
        doc_ref = self.db.collection(self.collection).document(str(doc.id))
        doc_snapshot = doc_ref.get()
        
        if doc_snapshot.exists:
            data = doc_snapshot.to_dict()
            updated_doc = self._dict_to_doc(doc_snapshot.id, data)
            # Update doc attributes
            for key, value in updated_doc.__dict__.items():
                setattr(doc, key, value)
    
    def delete(self, doc: Document) -> None:
        """Delete document from Firestore.
        
        Args:
            doc: Document instance
        """
        if hasattr(doc, "id") and doc.id:
            doc_ref = self.db.collection(self.collection).document(str(doc.id))
            doc_ref.delete()


class FirestoreQuery:
    """Query object that mimics SQLAlchemy query interface."""
    
    def __init__(self, collection_ref, model_class):
        self.collection_ref = collection_ref
        self.model_class = model_class
        self._filters = []
        self._order_by_field = None
        self._order_by_desc = False
    
    def filter(self, condition) -> "FirestoreQuery":
        """Add filter condition.
        
        Args:
            condition: SQLAlchemy-like filter condition
            
        Returns:
            Self for chaining
        """
        # Parse SQLAlchemy filter conditions
        # This is a simplified parser - handles common cases
        if hasattr(condition, "left") and hasattr(condition, "right"):
            # Binary condition (e.g., Document.owner_id == 1)
            field = condition.left.key if hasattr(condition.left, "key") else str(condition.left)
            value = condition.right.value if hasattr(condition.right, "value") else condition.right
            
            if hasattr(condition, "operator"):
                op = condition.operator.__name__ if hasattr(condition.operator, "__name__") else str(condition.operator)
                if op == "eq":
                    self._filters.append((field, "==", value))
                elif op == "ilike":
                    # Firestore doesn't have ILIKE, use case-insensitive search workaround
                    # For now, use equality (case-sensitive)
                    self._filters.append((field, "==", value))
        elif hasattr(condition, "left") and hasattr(condition, "right") and hasattr(condition, "comparator"):
            # Direct comparison (e.g., Document.status == "ready")
            field = condition.left.key if hasattr(condition.left, "key") else str(condition.left)
            value = condition.right
            
            # Determine operator from comparator
            if hasattr(condition, "comparator"):
                comp = condition.comparator
                if hasattr(comp, "__name__"):
                    if comp.__name__ == "eq":
                        self._filters.append((field, "==", value))
                    elif comp.__name__ == "ne":
                        self._filters.append((field, "!=", value))
        
        return self
    
    def order_by(self, field) -> "FirestoreQuery":
        """Add order by clause.
        
        Args:
            field: Field to order by (e.g., Document.id.desc())
            
        Returns:
            Self for chaining
        """
        # Parse order by field
        if hasattr(field, "key"):
            self._order_by_field = field.key
        elif hasattr(field, "desc"):
            # Handle .desc() call
            self._order_by_field = field.desc().key if hasattr(field.desc(), "key") else str(field)
            self._order_by_desc = True
        else:
            self._order_by_field = str(field)
        
        return self
    
    def all(self) -> List[Document]:
        """Execute query and return all results.
        
        Returns:
            List of Document instances
        """
        query = self.collection_ref
        
        # Apply filters
        for field, op, value in self._filters:
            if op == "==":
                query = query.where(field, "==", value)
            elif op == "!=":
                query = query.where(field, "!=", value)
        
        # Apply ordering
        if self._order_by_field:
            direction = firestore.Query.DESCENDING if self._order_by_desc else firestore.Query.ASCENDING
            query = query.order_by(self._order_by_field, direction=direction)
        
        # Execute query
        docs = []
        for doc_snapshot in query.stream():
            data = doc_snapshot.to_dict()
            doc = FirestoreDocumentAdapter()._dict_to_doc(doc_snapshot.id, data)
            docs.append(doc)
        
        return docs
    
    def count(self) -> int:
        """Count query results.
        
        Returns:
            Number of matching documents
        """
        query = self.collection_ref
        
        # Apply filters
        for field, op, value in self._filters:
            if op == "==":
                query = query.where(field, "==", value)
            elif op == "!=":
                query = query.where(field, "!=", value)
        
        # Count documents
        return len(list(query.stream()))


def get_firestore_db():
    """Get Firestore database adapter (compatible with get_db dependency).
    
    Yields:
        FirestoreDocumentAdapter instance
    """
    adapter = FirestoreDocumentAdapter()
    try:
        yield adapter
    finally:
        # Firestore client doesn't need explicit cleanup
        pass
