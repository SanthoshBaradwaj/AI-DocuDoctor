"""Celery-based task queue implementation."""
from celery import Celery
from celery.signals import setup_logging

from app.core.config import get_settings
from app.core.logging import setup_logging as setup_app_logging, get_logger
from app.infrastructure.queue.base import TaskQueue
from app.services.extract import naive_extract_from_minio, build_extracted
from app.infrastructure.storage.s3_minio import make_s3, get_bucket_name
from app.infrastructure.db.sql_alchemy import SessionLocal
from app.infrastructure.db.models import Document

settings = get_settings()
logger = get_logger(__name__)
BUCKET = get_bucket_name()

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


@celery_app.task
def process_document_ocr(document_id: int):
    """Background task to process OCR and extraction for a document.
    
    Args:
        document_id: The ID of the document to process
    """
    task_logger = get_logger(__name__)
    db = SessionLocal()
    try:
        doc = db.get(Document, document_id)
        if not doc:
            task_logger.error(
                "Document not found for OCR processing",
                extra={"document_id": document_id}
            )
            return {"error": f"Document {document_id} not found"}
        
        task_logger.info(
            "Starting OCR processing",
            extra={
                "document_id": document_id,
                "current_status": doc.status,
                "domain": doc.domain,
                "doc_type": doc.doc_type,
            }
        )
        
        # Update status to processing
        doc.status = "processing"
        db.commit()
        
        # Download file from storage
        s3 = make_s3()
        try:
            obj = s3.get_object(Bucket=BUCKET, Key=doc.s3_key)
            body_bytes = obj["Body"].read()
        except Exception as e:
            doc.status = "error"
            db.commit()
            task_logger.error(
                "Failed to download file for OCR",
                extra={
                    "document_id": document_id,
                    "storage_key": doc.s3_key,
                    "error": str(e),
                },
                exc_info=True
            )
            return {"error": f"Failed to download file: {str(e)}"}
        
        # Extract text (using current naive extraction)
        body, excerpt = naive_extract_from_minio(body_bytes, doc.filename)
        doc.body = body
        doc.excerpt = excerpt
        doc.extracted = build_extracted(body)
        doc.status = "ready"
        db.commit()
        
        task_logger.info(
            "OCR processing completed successfully",
            extra={
                "document_id": document_id,
                "domain": doc.domain,
                "doc_type": doc.doc_type,
                "expiry_date": str(doc.expiry_date) if doc.expiry_date else None,
                "extracted_fields_count": len(doc.extracted) if doc.extracted else 0,
            }
        )
        
        return {"success": True, "document_id": document_id}
    except Exception as e:
        task_logger.error(
            "OCR processing failed with exception",
            extra={
                "document_id": document_id,
                "error": str(e),
            },
            exc_info=True
        )
        # Try to update document status to error
        try:
            doc = db.get(Document, document_id)
            if doc:
                doc.status = "error"
                db.commit()
        except Exception:
            pass
        return {"error": f"OCR processing failed: {str(e)}"}
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
    if settings.QUEUE_BACKEND == "celery" or not settings.QUEUE_BACKEND:
        return CeleryTaskQueue()
    # Pub/Sub, SQS will be added later
    # For now, default to Celery
    return CeleryTaskQueue()
