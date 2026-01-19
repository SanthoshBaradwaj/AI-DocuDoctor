"""Celery-based task queue implementation."""
import time
from celery import Celery
from celery.signals import setup_logging
import httpx

from app.core.config import get_settings
from app.core.logging import setup_logging as setup_app_logging, get_logger
from app.core.constants import PipelineStepStatus
from app.infrastructure.queue.base import TaskQueue
from app.infrastructure.ai.base import get_ocr_service, get_llm_service
# Lazy import SessionLocal - only used when Celery is active (SQL mode)
def _get_session_local():
    """Get SQLAlchemy SessionLocal (lazy import to avoid engine creation in Firestore mode)."""
    from app.infrastructure.db.sql_alchemy import SessionLocal
    if SessionLocal is None:
        raise RuntimeError("SessionLocal not available: DB_PROVIDER is not 'sql' or DATABASE_URL is not set")
    return SessionLocal
from app.infrastructure.db.models import Document
from app.services.status import set_ocr_status, set_llm_status

settings = get_settings()
logger = get_logger(__name__)

# Use CELERY_BROKER_URL/CELERY_RESULT_BACKEND if provided, otherwise fall back to REDIS_URL
broker_url = settings.CELERY_BROKER_URL or settings.REDIS_URL or "redis://redis:6379/0"
result_backend = settings.CELERY_RESULT_BACKEND or settings.REDIS_URL or "redis://redis:6379/0"

celery_app = Celery(
    "doc_assistant",
    broker=broker_url,
    backend=result_backend,
)


@setup_logging.connect
def config_loggers(*args, **kwargs):
    """Configure Celery to use our application logging setup."""
    setup_app_logging()


@celery_app.task
def ping():
    return "pong"


@celery_app.task(
    bind=True,
    autoretry_for=(httpx.RequestError, httpx.HTTPStatusError,),
    retry_backoff=True,
    max_retries=3,
)
def process_document_ocr(self, document_id: int):
    """Background task to process OCR and extraction for a document.
    
    Args:
        self: Celery task instance (bound task)
        document_id: The ID of the document to process
    """
    task_logger = get_logger(__name__)
    start_time = time.monotonic()
    db = _get_session_local()()
    celery_task_id = self.request.id if hasattr(self.request, 'id') else None
    
    try:
        doc = db.get(Document, document_id)
        if not doc:
            task_logger.warning(
                "Document not found for OCR processing",
                extra={
                    "document_id": document_id,
                    "celery_task_id": celery_task_id,
                }
            )
            return {"error": f"Document {document_id} not found"}
        
        # Get OCR service to determine provider
        ocr_service = get_ocr_service()
        provider = settings.OCR_PROVIDER or "fake"
        provider_name = type(ocr_service).__name__
        
        task_logger.info(
            "OCR processing started",
            extra={
                "event": "ocr.started",
                "document_id": document_id,
                "celery_task_id": celery_task_id,
                "current_status": doc.status,
                "ocr_status": doc.ocr_status,
                "domain": doc.domain,
                "doc_type": doc.doc_type,
                "provider": provider,
                "provider_name": provider_name,
                "storage_key": doc.s3_key,
                "mime_type": doc.mime,
            }
        )
        
        # Set status to processing if not already
        if doc.status != "processing":
            doc.status = "processing"
        # Set OCR status to processing using helper
        set_ocr_status(doc, PipelineStepStatus.PROCESSING, reason="OCR task started")
        db.commit()
        
        # Get OCR service via abstraction
        ocr_service = get_ocr_service()
        
        # Call OCR service to extract document
        ocr_result = ocr_service.extract_document(
            storage_key=doc.s3_key,
            mime_type=doc.mime,
        )
        
        # Update document with OCR results
        doc.body = ocr_result.text
        
        # Generate excerpt (first 300 characters, safely handling empty text)
        if ocr_result.text:
            excerpt = ocr_result.text[:300].strip()
            # If we cut off mid-word, try to cut at a space
            if len(ocr_result.text) > 300:
                last_space = excerpt.rfind(' ')
                if last_space > 200:  # Only use space if it's not too early
                    excerpt = excerpt[:last_space]
            doc.excerpt = excerpt
        else:
            doc.excerpt = ""
        
        # Store OCR metadata in extracted field with provider info
        # Preserve existing extracted data if present
        extracted_data = doc.extracted or {}
        extracted_data["ocr"] = {
            "page_count": ocr_result.page_count,
            "language": ocr_result.language,
            "provider": provider,
            "provider_name": provider_name,
        }
        doc.extracted = extracted_data
        
        # Update status to ready
        doc.status = "ready"
        set_ocr_status(doc, PipelineStepStatus.READY, reason="OCR completed successfully")
        db.commit()
        
        duration_ms = (time.monotonic() - start_time) * 1000
        
        # Get request_id from document if available
        request_id = doc.request_id if hasattr(doc, 'request_id') else None
        
        task_logger.info(
            "OCR processing completed successfully",
            extra={
                "event": "ocr.success",
                "document_id": document_id,
                "celery_task_id": celery_task_id,
                "request_id": request_id,
                "status": doc.status,
                "ocr_status": doc.ocr_status,
                "page_count": ocr_result.page_count,
                "language": ocr_result.language,
                "domain": doc.domain,
                "doc_type": doc.doc_type,
                "provider": provider,
                "provider_name": provider_name,
                "text_length": len(ocr_result.text),
                "duration_ms": round(duration_ms, 2),
            }
        )
        
        # Enqueue LLM analysis task after OCR completes
        process_document_llm.delay(document_id)
        
        return {"success": True, "document_id": document_id}
    except Exception as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        provider = settings.OCR_PROVIDER or "fake"
        
        # Check if this is a transient error that should trigger retry
        is_transient = isinstance(e, (httpx.RequestError, httpx.HTTPStatusError))
        
        # Try to get request_id from document
        request_id = None
        try:
            doc = db.get(Document, document_id)
            if doc and hasattr(doc, 'request_id'):
                request_id = doc.request_id
        except Exception:
            pass
        
        task_logger.error(
            "OCR processing failed",
            extra={
                "event": "ocr.failure",
                "document_id": document_id,
                "celery_task_id": celery_task_id,
                "request_id": request_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "provider": provider,
                "is_transient": is_transient,
                "duration_ms": round(duration_ms, 2),
            },
            exc_info=True
        )
        
        # Only update status to error if this is not a transient error (transient errors will retry)
        # Or if we've exhausted retries
        if not is_transient or self.request.retries >= self.max_retries:
            try:
                doc = db.get(Document, document_id)
                if doc:
                    doc.status = "error"
                    set_ocr_status(doc, PipelineStepStatus.ERROR, reason=f"OCR failed: {type(e).__name__}")
                    db.commit()
            except Exception:
                pass
        
        # Re-raise transient errors to trigger Celery retry
        if is_transient:
            raise
        
        return {"error": f"OCR processing failed: {str(e)}"}
    finally:
        db.close()


@celery_app.task(
    bind=True,
    autoretry_for=(httpx.RequestError, httpx.HTTPStatusError,),
    retry_backoff=True,
    max_retries=3,
)
def process_document_llm(self, document_id: int):
    """Background task to run LLM analysis on a document after OCR.
    
    Args:
        self: Celery task instance (bound task)
        document_id: The ID of the document to analyze
    """
    task_logger = get_logger(__name__)
    start_time = time.monotonic()
    db = _get_session_local()()
    celery_task_id = self.request.id if hasattr(self.request, 'id') else None
    
    try:
        doc = db.get(Document, document_id)
        if not doc:
            task_logger.warning(
                "Document not found for LLM analysis",
                extra={
                    "document_id": document_id,
                    "celery_task_id": celery_task_id,
                }
            )
            return {"error": f"Document {document_id} not found"}
        
        # Ensure OCR has already run (body should be populated)
        if not doc.body or doc.status != "ready":
            task_logger.warning(
                "Document not ready for LLM analysis (OCR may not have completed)",
                extra={
                    "document_id": document_id,
                    "celery_task_id": celery_task_id,
                    "status": doc.status,
                    "ocr_status": doc.ocr_status,
                    "has_body": bool(doc.body),
                }
            )
            # Set LLM status to error since we can't proceed (non-transient error, no retry)
            set_llm_status(doc, PipelineStepStatus.ERROR, reason="OCR not completed")
            db.commit()
            return {"error": f"Document {document_id} not ready for analysis (status: {doc.status})"}
        
        # Get LLM service to determine provider
        llm_service = get_llm_service()
        provider = settings.LLM_PROVIDER or "fake"
        provider_name = type(llm_service).__name__
        
        # Get request_id from document if available
        request_id = doc.request_id if hasattr(doc, 'request_id') else None
        
        task_logger.info(
            "LLM analysis started",
            extra={
                "event": "llm.started",
                "document_id": document_id,
                "celery_task_id": celery_task_id,
                "request_id": request_id,
                "domain": doc.domain,
                "doc_type": doc.doc_type,
                "text_length": len(doc.body),
                "ocr_status": doc.ocr_status,
                "llm_status": doc.llm_status,
                "provider": provider,
                "provider_name": provider_name,
                "mime_type": doc.mime,
            }
        )
        
        # Set LLM status to processing using helper
        set_llm_status(doc, PipelineStepStatus.PROCESSING, reason="LLM task started")
        db.commit()
        
        # Call LLM service to analyze document
        llm_result = llm_service.analyze_document(
            text=doc.body,
            mime_type=doc.mime,
            doc_type=doc.doc_type,
        )
        
        # Update document with LLM results (preserve existing extracted data)
        extracted_data = doc.extracted or {}
        extracted_data["llm"] = {
            "summary": llm_result.summary,
            "entities": llm_result.entities,
            "provider": provider,
            "provider_name": provider_name,
        }
        # Preserve top-level fields for backward compatibility
        extracted_data["summary"] = llm_result.summary
        extracted_data["entities"] = llm_result.entities
        doc.extracted = extracted_data
        
        # Update LLM status to ready
        set_llm_status(doc, PipelineStepStatus.READY, reason="LLM analysis completed successfully")
        db.commit()
        
        duration_ms = (time.monotonic() - start_time) * 1000
        
        # Get request_id from document if available
        request_id = doc.request_id if hasattr(doc, 'request_id') else None
        
        task_logger.info(
            "LLM analysis completed successfully",
            extra={
                "event": "llm.success",
                "document_id": document_id,
                "celery_task_id": celery_task_id,
                "request_id": request_id,
                "summary_length": len(llm_result.summary),
                "entities_count": len(llm_result.entities),
                "llm_status": doc.llm_status,
                "domain": doc.domain,
                "doc_type": doc.doc_type,
                "provider": provider,
                "provider_name": provider_name,
                "duration_ms": round(duration_ms, 2),
            }
        )
        
        return {"success": True, "document_id": document_id}
    except Exception as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        provider = settings.LLM_PROVIDER or "fake"
        
        # Check if this is a transient error that should trigger retry
        is_transient = isinstance(e, (httpx.RequestError, httpx.HTTPStatusError))
        
        # Try to get request_id from document
        request_id = None
        try:
            doc = db.get(Document, document_id)
            if doc and hasattr(doc, 'request_id'):
                request_id = doc.request_id
        except Exception:
            pass
        
        task_logger.error(
            "LLM analysis failed",
            extra={
                "event": "llm.failure",
                "document_id": document_id,
                "celery_task_id": celery_task_id,
                "request_id": request_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "provider": provider,
                "is_transient": is_transient,
                "duration_ms": round(duration_ms, 2),
            },
            exc_info=True
        )
        
        # Only update status to error if this is not a transient error (transient errors will retry)
        # Or if we've exhausted retries
        if not is_transient or self.request.retries >= self.max_retries:
            try:
                doc = db.get(Document, document_id)
                if doc:
                    set_llm_status(doc, PipelineStepStatus.ERROR, reason=f"LLM failed: {type(e).__name__}")
                    db.commit()
            except Exception:
                pass
        
        # Re-raise transient errors to trigger Celery retry
        if is_transient:
            raise
        
        return {"error": f"LLM analysis failed: {str(e)}"}
    finally:
        db.close()


class CeleryTaskQueue:
    """Celery-based implementation of TaskQueue."""
    
    def enqueue_ocr(self, document_id: int) -> None:
        """Enqueue an OCR task for a document using Celery.
        
        Args:
            document_id: The ID of the document to process
        """
        logger.info(
            "Enqueuing OCR task via Celery",
            extra={
                "document_id": document_id,
                "queue_backend": "celery",
            }
        )
        
        task = process_document_ocr.delay(document_id)
        
        logger.info(
            "OCR task queued successfully",
            extra={
                "document_id": document_id,
                "task_id": task.id,
                "queue_backend": "celery",
            }
        )


def get_task_queue() -> TaskQueue:
    """Get the appropriate task queue implementation based on configuration.
    
    Returns:
        TaskQueue implementation
    """
    # Check TASK_QUEUE_PROVIDER first, then fall back to QUEUE_BACKEND
    provider = getattr(settings, "TASK_QUEUE_PROVIDER", None) or settings.QUEUE_BACKEND or "celery"
    
    if provider == "http":
        from app.infrastructure.queue.http_queue import HttpTaskQueue
        return HttpTaskQueue()
    elif provider == "celery" or not provider:
        return CeleryTaskQueue()
    # Cloud Tasks, Pub/Sub, SQS will be added later
    # Default to Celery for backward compatibility
    return CeleryTaskQueue()
