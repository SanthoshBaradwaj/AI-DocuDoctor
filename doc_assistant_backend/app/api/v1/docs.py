from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_
import uuid
from typing import Optional

from app.core.config import get_settings
from app.core.logging import get_logger
from app.infrastructure.db.sql_alchemy import get_db
from app.infrastructure.db.models import Document
from app.schemas import (
    DocOut, DocDetailOut, UploadInitIn, UploadInitOut, UploadNotifyIn,
    AnalyzeIn, BatchAnalyzeIn  # Keep for backward compatibility
)
from app.infrastructure.storage.storage_factory import get_storage_backend
from app.infrastructure.queue.celery_queue import get_task_queue
from app.domain.documents.doc_types import DocumentDomain, DocumentType

router = APIRouter(prefix="/api/v1/docs", tags=["docs"])
logger = get_logger(__name__)
settings = get_settings()


@router.get("", response_model=list[DocOut])
def list_docs(
    db: Session = Depends(get_db),
    domain: Optional[str] = Query(None, description="Filter by document domain"),
    doc_type: Optional[str] = Query(None, description="Filter by document type"),
    status: Optional[str] = Query(None, description="Filter by document status"),
):
    """List documents for the current user with optional filtering."""
    # For now, assume single user (owner_id=1) until real auth is wired
    query = db.query(Document).filter(Document.owner_id == 1)
    
    # Apply filters
    if domain:
        query = query.filter(Document.domain.ilike(domain))
    if doc_type:
        query = query.filter(Document.doc_type.ilike(doc_type))
    if status:
        query = query.filter(Document.status == status)
    
    return query.order_by(Document.id.desc()).all()


@router.get("/{doc_id}", response_model=DocDetailOut)
def get_doc(doc_id: int, db: Session = Depends(get_db)):
    """Get full details of a single document."""
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Not found")
    return doc


@router.post("/upload/presign", response_model=UploadInitOut)
def get_presigned_upload(
    payload: UploadInitIn,
    request: Request,
    db: Session = Depends(get_db)
):
    """Initialize an upload and get presigned URL.
    
    This is the future-proof upload entry point that uses StorageBackend abstraction.
    """
    request_id = getattr(request.state, "request_id", None)
    user_id = 1  # Placeholder until real auth
    
    # Generate unique storage key
    storage_key = f"user_{user_id}/{uuid.uuid4().hex}/{payload.filename}"
    max_size_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    
    logger.info(
        "Upload initialization",
        extra={
            "request_id": request_id,
            "user_id": user_id,
            "storage_key": storage_key,
            "file_name": payload.filename,
            "mime_type": payload.mime_type,
            "size_bytes": payload.size_bytes,
            "max_size_bytes": max_size_bytes,
            "domain_hint": payload.domain,
            "doc_type_hint": payload.doc_type,
        }
    )
    
    # Get storage backend (abstracted)
    storage = get_storage_backend()
    
    # Generate presigned upload URL
    presign_result = storage.presign_upload(
        key=storage_key,
        content_type=payload.mime_type
    )
    
    return UploadInitOut(
        storage_key=storage_key,
        upload_url=presign_result["url"],
        upload_fields=presign_result.get("fields"),
        max_size_bytes=max_size_bytes,
    )


@router.post("/notify", response_model=DocDetailOut)
def notify_uploaded(
    payload: UploadNotifyIn,
    request: Request,
    db: Session = Depends(get_db)
):
    """Notify the backend that file upload is complete and kick off async processing.
    
    Creates a DB record and enqueues OCR/extraction task.
    """
    request_id = getattr(request.state, "request_id", None)
    
    # Validate domain and doc_type if provided
    domain_value = None
    doc_type_value = None
    
    if payload.domain:
        try:
            domain_value = DocumentDomain(payload.domain.upper()).value
        except ValueError:
            # Invalid domain, ignore it
            logger.warning(
                "Invalid domain provided",
                extra={"request_id": request_id, "domain": payload.domain}
            )
    
    if payload.doc_type:
        try:
            doc_type_value = DocumentType(payload.doc_type.upper()).value
        except ValueError:
            # Invalid doc_type, ignore it
            logger.warning(
                "Invalid doc_type provided",
                extra={"request_id": request_id, "doc_type": payload.doc_type}
            )
    
    # Create document record
    doc = Document(
        owner_id=1,  # Single user for now
        title=payload.filename,
        filename=payload.filename,
        s3_key=payload.storage_key,
        size=payload.size_bytes,
        mime=payload.mime_type,
        status="processing",  # Will be updated by background task
        domain=domain_value,
        doc_type=doc_type_value,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    logger.info(
        "Document upload notified, enqueuing OCR",
        extra={
            "request_id": request_id,
            "document_id": doc.id,
            "domain": domain_value,
            "doc_type": doc_type_value,
            "filename": payload.filename,
            "storage_key": payload.storage_key,
            "size_bytes": payload.size_bytes,
        }
    )
    
    # Enqueue OCR task (async processing) via TaskQueue abstraction
    task_queue = get_task_queue()
    task_queue.enqueue_ocr(doc.id)
    
    logger.info(
        "OCR task enqueued via TaskQueue",
        extra={
            "request_id": request_id,
            "document_id": doc.id,
            "queue_backend": settings.QUEUE_BACKEND or "celery",
        }
    )
    
    return doc


@router.post("/analyze", response_model=DocDetailOut)
def analyze_one(payload: AnalyzeIn, db: Session = Depends(get_db)):
    """Analyze a single document.
    
    TODO: This endpoint is transitional and will be superseded by the new async pipeline
    once OCR + LLM are fully wired. The /notify endpoint now handles async processing.
    """
    doc = db.get(Document, payload.docId)
    if not doc:
        raise HTTPException(404, "Not found")
    
    # For now, keep the existing synchronous extraction logic
    from app.services.extract import build_extracted
    doc.extracted = build_extracted(doc.body)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.post("/analyze/batch", response_model=list[DocOut])
def analyze_batch(payload: BatchAnalyzeIn, db: Session = Depends(get_db)):
    """Analyze multiple documents.
    
    TODO: This endpoint is transitional and will be superseded by the new async pipeline.
    """
    out = []
    from app.services.extract import build_extracted
    
    for did in payload.docIds:
        doc = db.get(Document, did)
        if not doc:
            continue
        doc.extracted = build_extracted(doc.body)
        db.add(doc)
        out.append(doc)
    db.commit()
    return out


@router.get("/{doc_id}/download")
def presigned_download(doc_id: int, db: Session = Depends(get_db)):
    """Return a short-lived URL to download the original file from storage."""
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Not found")
    
    storage = get_storage_backend()
    url = storage.presign_download(doc.s3_key, expires_in=300)  # 5 minutes
    return {"url": url}
