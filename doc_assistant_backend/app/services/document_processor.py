"""Shared document processing logic for OCR and LLM."""
import time
from typing import Literal, Optional
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.constants import PipelineStepStatus
from app.infrastructure.ai.base import get_ocr_service, get_llm_service
from app.infrastructure.db.models import Document
from app.services.status import set_ocr_status, set_llm_status

settings = get_settings()
logger = get_logger(__name__)


def process_document_ocr_sync(doc: Document, db) -> dict:
    """Process OCR for a document synchronously (shared logic for Celery and HTTP).
    
    Args:
        doc: Document instance
        db: Database session/adapter
        
    Returns:
        Dict with success status and metadata
    """
    start_time = time.monotonic()
    document_id = doc.id
    
    try:
        # Get OCR service to determine provider
        ocr_service = get_ocr_service()
        provider = settings.OCR_PROVIDER or "fake"
        provider_name = type(ocr_service).__name__
        
        logger.info(
            "OCR processing started",
            extra={
                "event": "ocr.started",
                "document_id": document_id,
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
        request_id = doc.request_id if hasattr(doc, 'request_id') else None
        
        logger.info(
            "OCR processing completed successfully",
            extra={
                "event": "ocr.success",
                "document_id": document_id,
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
        
        return {
            "success": True,
            "document_id": document_id,
            "step": "ocr",
            "page_count": ocr_result.page_count,
            "language": ocr_result.language,
        }
    except Exception as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        provider = settings.OCR_PROVIDER or "fake"
        request_id = doc.request_id if hasattr(doc, 'request_id') else None
        
        logger.error(
            "OCR processing failed",
            extra={
                "event": "ocr.failure",
                "document_id": document_id,
                "request_id": request_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "provider": provider,
                "duration_ms": round(duration_ms, 2),
            },
            exc_info=True
        )
        
        # Update status to error
        try:
            doc.status = "error"
            set_ocr_status(doc, PipelineStepStatus.ERROR, reason=f"OCR failed: {type(e).__name__}")
            db.commit()
        except Exception:
            pass
        
        raise


def process_document_llm_sync(doc: Document, db) -> dict:
    """Process LLM analysis for a document synchronously (shared logic for Celery and HTTP).
    
    Args:
        doc: Document instance
        db: Database session/adapter
        
    Returns:
        Dict with success status and metadata
    """
    start_time = time.monotonic()
    document_id = doc.id
    
    try:
        # Ensure OCR has already run (body should be populated)
        if not doc.body or doc.status != "ready":
            logger.warning(
                "Document not ready for LLM analysis (OCR may not have completed)",
                extra={
                    "document_id": document_id,
                    "status": doc.status,
                    "ocr_status": doc.ocr_status,
                    "has_body": bool(doc.body),
                }
            )
            # Set LLM status to error since we can't proceed
            set_llm_status(doc, PipelineStepStatus.ERROR, reason="OCR not completed")
            db.commit()
            raise ValueError(f"Document {document_id} not ready for analysis (status: {doc.status})")
        
        # Get LLM service to determine provider
        llm_service = get_llm_service()
        provider = settings.LLM_PROVIDER or "fake"
        provider_name = type(llm_service).__name__
        
        request_id = doc.request_id if hasattr(doc, 'request_id') else None
        
        logger.info(
            "LLM analysis started",
            extra={
                "event": "llm.started",
                "document_id": document_id,
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
        
        logger.info(
            "LLM analysis completed successfully",
            extra={
                "event": "llm.success",
                "document_id": document_id,
                "request_id": request_id,
                "domain": doc.domain,
                "doc_type": doc.doc_type,
                "text_length": len(doc.body),
                "ocr_status": doc.ocr_status,
                "llm_status": doc.llm_status,
                "provider": provider,
                "provider_name": provider_name,
                "summary_length": len(llm_result.summary),
                "entities_count": len(llm_result.entities),
                "duration_ms": round(duration_ms, 2),
            }
        )
        
        return {
            "success": True,
            "document_id": document_id,
            "step": "llm",
            "summary_length": len(llm_result.summary),
            "entities_count": len(llm_result.entities),
        }
    except Exception as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        provider = settings.LLM_PROVIDER or "fake"
        request_id = doc.request_id if hasattr(doc, 'request_id') else None
        
        logger.error(
            "LLM analysis failed",
            extra={
                "event": "llm.failure",
                "document_id": document_id,
                "request_id": request_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "provider": provider,
                "duration_ms": round(duration_ms, 2),
            },
            exc_info=True
        )
        
        # Update LLM status to error
        try:
            set_llm_status(doc, PipelineStepStatus.ERROR, reason=f"LLM failed: {type(e).__name__}")
            db.commit()
        except Exception:
            pass
        
        raise
