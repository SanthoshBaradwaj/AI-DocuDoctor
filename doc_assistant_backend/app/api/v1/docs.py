from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_
import uuid
from typing import Optional, Literal

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.errors import normalize_error_response, map_status_to_error_code
from app.core.constants import PipelineStepStatus
from app.infrastructure.db.db_factory import get_db
from app.infrastructure.db.models import Document
from app.infrastructure.db.db_helpers import get_document
from app.schemas import (
    DocOut, DocDetailOut, UploadInitIn, UploadInitOut, UploadNotifyIn,
    AnalyzeIn, BatchAnalyzeIn  # Keep for backward compatibility
)
from app.infrastructure.storage.storage_factory import get_storage_backend
from app.infrastructure.queue.celery_queue import get_task_queue
from app.domain.documents.doc_types import DocumentDomain, DocumentType
from app.services.status import set_ocr_status, set_llm_status
from app.services.document_processor import process_document_ocr_sync, process_document_llm_sync
from pydantic import BaseModel

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
def get_doc(doc_id: str, db: Session = Depends(get_db)):
    """Get full details of a single document."""
    # Self-check: Log database backend type for debugging
    from app.infrastructure.db.db_helpers import is_firestore_adapter
    is_firestore = is_firestore_adapter(db)
    logger.debug(
        "Get document request",
        extra={
            "doc_id": doc_id,
            "db_backend": "firestore" if is_firestore else "sqlalchemy",
            "db_class": db.__class__.__name__,
        }
    )
    
    request_id = getattr(request.state, "request_id", None)
    doc = get_document(db, doc_id)
    if not doc:
        error_response = normalize_error_response(
            error_code="NOT_FOUND",
            message="Document not found",
            details={"doc_id": doc_id},
            request_id=request_id,
        )
        raise HTTPException(status_code=404, detail=error_response)
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
        request_id=request_id,  # Store request ID for traceability
    )
    # Initialize status fields using helpers
    set_ocr_status(doc, PipelineStepStatus.PENDING, reason="Document created")
    set_llm_status(doc, PipelineStepStatus.PENDING, reason="Document created")
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
            "file_name": payload.filename,
            "storage_key": payload.storage_key,
            "size_bytes": payload.size_bytes,
        }
    )
    
    # Enqueue OCR task (async processing) via TaskQueue abstraction
    task_queue = get_task_queue()
    task_queue.enqueue_ocr(doc.id)
    
    # Get task queue provider name for logging
    task_queue_provider = getattr(settings, "TASK_QUEUE_PROVIDER", None) or settings.QUEUE_BACKEND or "celery"
    
    logger.info(
        "OCR task enqueued via TaskQueue",
        extra={
            "request_id": request_id,
            "document_id": doc.id,
            "queue_backend": task_queue_provider,
        }
    )
    
    return doc


class ProcessRequest(BaseModel):
    """Request model for document processing endpoint."""
    step: Optional[Literal["ocr", "llm", "all"]] = "all"  # Which step(s) to process


@router.post("/{doc_id}/process", response_model=dict)
def process_document(
    doc_id: str,
    payload: ProcessRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Process a document (OCR and/or LLM analysis).
    
    This endpoint can be called synchronously or asynchronously (via HTTP task queue).
    In cloud mode, /notify calls this endpoint via HTTP task queue.
    
    Args:
        doc_id: Document ID to process
        payload: Processing request with optional step specification
        request: FastAPI request object
        db: Database session
        
    Returns:
        Dict with processing results
    """
    request_id = getattr(request.state, "request_id", None)
    
    # Self-check: Log database backend type for debugging
    from app.infrastructure.db.db_helpers import is_firestore_adapter
    is_firestore = is_firestore_adapter(db)
    logger.debug(
        "Process document request",
        extra={
            "request_id": request_id,
            "doc_id": doc_id,
            "db_backend": "firestore" if is_firestore else "sqlalchemy",
            "db_class": db.__class__.__name__,
        }
    )
    
    # Get document
    doc = get_document(db, doc_id)
    if not doc:
        error_response = normalize_error_response(
            error_code="NOT_FOUND",
            message=f"Document {doc_id} not found",
            details={"doc_id": doc_id},
            request_id=request_id,
        )
        raise HTTPException(status_code=404, detail=error_response)
    
    logger.info(
        "Document processing requested",
        extra={
            "request_id": request_id,
            "document_id": doc_id,
            "step": payload.step,
            "current_status": doc.status,
            "ocr_status": doc.ocr_status,
            "llm_status": doc.llm_status,
        }
    )
    
    results = {}
    
    # Process OCR if requested
    if payload.step in ["ocr", "all"]:
        if doc.ocr_status != PipelineStepStatus.READY.value:
            ocr_result = process_document_ocr_sync(doc, db)
            results["ocr"] = ocr_result
            # Refresh doc after OCR
            db.refresh(doc)
        else:
            results["ocr"] = {"success": True, "message": "OCR already completed"}
    
    # Process LLM if requested
    if payload.step in ["llm", "all"]:
        if doc.llm_status != PipelineStepStatus.READY.value:
            llm_result = process_document_llm_sync(doc, db)
            results["llm"] = llm_result
            # Refresh doc after LLM
            db.refresh(doc)
        else:
            results["llm"] = {"success": True, "message": "LLM already completed"}
    
    # Re-fetch document from DB to get latest persisted values
    doc = get_document(db, doc_id)
    if not doc:
        error_response = normalize_error_response(
            error_code="NOT_FOUND",
            message=f"Document {doc_id} not found after processing",
            details={"doc_id": doc_id},
            request_id=request_id,
        )
        raise HTTPException(status_code=404, detail=error_response)
    
    # Determine overall success (all requested steps succeeded)
    overall_success = all(
        result.get("success", False) 
        for result in results.values() 
        if isinstance(result, dict)
    )
    
    logger.info(
        "Document processing completed",
        extra={
            "request_id": request_id,
            "document_id": doc_id,
            "step": payload.step,
            "overall_success": overall_success,
            "results": results,
            "final_status": doc.status,
            "final_ocr_status": doc.ocr_status,
            "final_llm_status": doc.llm_status,
            "has_body": bool(doc.body),
            "body_length": len(doc.body) if doc.body else 0,
        }
    )
    
    # Always return 200, even if some steps failed (errors are stored in DB)
    return {
        "success": overall_success,
        "document_id": doc_id,
        "step": payload.step,
        "status": doc.status,
        "ocr_status": doc.ocr_status,
        "llm_status": doc.llm_status,
        "results": results,
    }


@router.post("/analyze", response_model=DocDetailOut)
def analyze_one(
    payload: AnalyzeIn,
    request: Request,
    db: Session = Depends(get_db)
):
    """Analyze a single document.
    
    TODO: This endpoint is transitional and will be superseded by the new async pipeline
    once OCR + LLM are fully wired. The /notify endpoint now handles async processing.
    
    This endpoint now uses the LlmService abstraction instead of direct extraction logic.
    """
    request_id = getattr(request.state, "request_id", None)
    doc = get_document(db, payload.docId)
    if not doc:
        error_response = normalize_error_response(
            error_code="NOT_FOUND",
            message="Document not found",
            details={"doc_id": payload.docId},
            request_id=request_id,
        )
        raise HTTPException(status_code=404, detail=error_response)
    
    # Use LlmService abstraction instead of direct extraction
    from app.infrastructure.ai.base import get_llm_service
    
    if not doc.body:
        error_response = normalize_error_response(
            error_code="VALIDATION_ERROR",
            message="Document has no text content. OCR may not have completed yet.",
            details={"doc_id": payload.docId},
            request_id=request_id,
        )
        raise HTTPException(status_code=400, detail=error_response)
    
    llm_service = get_llm_service()
    llm_result = llm_service.analyze_document(
        text=doc.body,
        mime_type=doc.mime,
        doc_type=doc.doc_type,
    )
    
    # Update document with LLM results (same fields as before)
    doc.extracted = {
        "summary": llm_result.summary,
        "entities": llm_result.entities,
    }
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.post("/analyze/batch", response_model=list[DocOut])
def analyze_batch(payload: BatchAnalyzeIn, db: Session = Depends(get_db)):
    """Analyze multiple documents.
    
    TODO: This endpoint is transitional and will be superseded by the new async pipeline.
    
    This endpoint now uses the LlmService abstraction instead of direct extraction logic.
    """
    out = []
    from app.infrastructure.ai.base import get_llm_service
    
    llm_service = get_llm_service()
    
    for did in payload.docIds:
        doc = get_document(db, did)
        if not doc:
            continue
        
        if not doc.body:
            # Skip documents without text content
            continue
        
        llm_result = llm_service.analyze_document(
            text=doc.body,
            mime_type=doc.mime,
            doc_type=doc.doc_type,
        )
        
        # Update document with LLM results (same fields as before)
        doc.extracted = {
            "summary": llm_result.summary,
            "entities": llm_result.entities,
        }
        db.add(doc)
        out.append(doc)
    db.commit()
    return out


@router.post("/{doc_id}/reprocess/ocr")
def reprocess_ocr(
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Reprocess OCR for a document.
    
    Resets OCR and LLM statuses to pending and enqueues OCR task.
    This will trigger a fresh OCR run, followed by LLM analysis.
    """
    request_id = getattr(request.state, "request_id", None)
    doc = get_document(db, doc_id)
    if not doc:
        error_response = normalize_error_response(
            error_code="NOT_FOUND",
            message="Document not found",
            details={"doc_id": doc_id},
            request_id=request_id,
        )
        raise HTTPException(status_code=404, detail=error_response)
    
    # Reset statuses for reprocessing using helpers
    doc.status = "processing"
    set_ocr_status(doc, PipelineStepStatus.PENDING, reason="OCR reprocessing requested")
    set_llm_status(doc, PipelineStepStatus.PENDING, reason="OCR reprocessing requested (LLM will be recomputed)")
    db.commit()
    
    # Enqueue OCR task
    task_queue = get_task_queue()
    task_queue.enqueue_ocr(doc.id)
    
    logger.info(
        "OCR reprocessing scheduled",
        extra={
            "document_id": doc_id,
            "queue_backend": settings.QUEUE_BACKEND or "celery",
        }
    )
    
    return {"message": "OCR reprocessing scheduled", "document_id": doc_id}


@router.post("/{doc_id}/reprocess/llm")
def reprocess_llm(
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Reprocess LLM analysis for a document.
    
    Requires that OCR has already completed (document.body must be present).
    Resets LLM status to pending and enqueues LLM task.
    """
    request_id = getattr(request.state, "request_id", None)
    doc = get_document(db, doc_id)
    if not doc:
        error_response = normalize_error_response(
            error_code="NOT_FOUND",
            message="Document not found",
            details={"doc_id": doc_id},
            request_id=request_id,
        )
        raise HTTPException(status_code=404, detail=error_response)
    
    # Verify OCR has completed
    if not doc.body:
        error_response = normalize_error_response(
            error_code="VALIDATION_ERROR",
            message="OCR not completed; cannot reprocess LLM. Document has no text content.",
            details={"doc_id": doc_id},
            request_id=request_id,
        )
        raise HTTPException(status_code=400, detail=error_response)
    
    # Reset LLM status for reprocessing using helper
    set_llm_status(doc, PipelineStepStatus.PENDING, reason="LLM reprocessing requested")
    db.commit()
    
    # Enqueue LLM task
    from app.infrastructure.queue.celery_queue import process_document_llm
    process_document_llm.delay(doc.id)
    
    logger.info(
        "LLM reprocessing scheduled",
        extra={
            "document_id": doc_id,
            "queue_backend": settings.QUEUE_BACKEND or "celery",
        }
    )
    
    return {"message": "LLM reprocessing scheduled", "document_id": doc_id}


@router.get("/{doc_id}/download")
def presigned_download(
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Return a short-lived URL to download the original file from storage."""
    request_id = getattr(request.state, "request_id", None)
    doc = get_document(db, doc_id)
    if not doc:
        error_response = normalize_error_response(
            error_code="NOT_FOUND",
            message="Document not found",
            details={"doc_id": doc_id},
            request_id=request_id,
        )
        raise HTTPException(status_code=404, detail=error_response)
    
    storage = get_storage_backend()
    url = storage.presign_download(doc.s3_key, expires_in=300)  # 5 minutes
    return {"url": url}


@router.get("/{doc_id}/status", response_model=dict)
def get_doc_status(
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Get document processing status and last error (if any).
    
    Returns:
        Dict with status, ocr_status, llm_status, and last_error fields
    """
    request_id = getattr(request.state, "request_id", None)
    doc = get_document(db, doc_id)
    if not doc:
        error_response = normalize_error_response(
            error_code="NOT_FOUND",
            message="Document not found",
            details={"doc_id": doc_id},
            request_id=request_id,
        )
        raise HTTPException(status_code=404, detail=error_response)
    
    # Extract error messages from extracted field
    extracted = doc.extracted or {}
    ocr_error = extracted.get("ocr_error")
    llm_error = extracted.get("llm_error")
    
    # Determine last error (prefer OCR error if both exist, as OCR runs first)
    last_error = ocr_error or llm_error
    
    return {
        "document_id": doc_id,
        "status": doc.status,
        "ocr_status": doc.ocr_status,
        "llm_status": doc.llm_status,
        "last_error": last_error,
        "ocr_error": ocr_error,
        "llm_error": llm_error,
    }
