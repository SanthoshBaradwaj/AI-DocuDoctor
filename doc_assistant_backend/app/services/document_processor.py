"""Shared document processing logic for OCR and LLM."""
import time
from typing import Literal, Optional
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.constants import PipelineStepStatus
from app.infrastructure.ai.base import get_ocr_service, get_llm_service, OcrResult
from app.infrastructure.db.models import Document
from app.services.status import set_ocr_status, set_llm_status
from app.infrastructure.storage.storage_reader import read_text_file
from app.infrastructure.db.db_helpers import update_document, is_firestore_adapter

settings = get_settings()
logger = get_logger(__name__)


def process_document_ocr_sync(doc: Document, db) -> dict:
    """Process OCR for a document synchronously (shared logic for Celery and HTTP).
    
    Args:
        doc: Document instance
        db: Database session/adapter
        
    Returns:
        Dict with success status and metadata (never raises, always returns)
    """
    start_time = time.monotonic()
    document_id = doc.id
    request_id = doc.request_id if hasattr(doc, 'request_id') else None
    
    # Step 1: Initialize
    try:
        # Get OCR service to determine provider
        ocr_service = get_ocr_service()
        provider = settings.OCR_PROVIDER or "fake"
        provider_name = type(ocr_service).__name__
        provider_url = getattr(ocr_service, 'base_url', None) if hasattr(ocr_service, 'base_url') else None
        
        logger.info(
            "OCR processing started",
            extra={
                "event": "ocr.started",
                "request_id": request_id,
                "document_id": document_id,
                "current_status": doc.status,
                "ocr_status": doc.ocr_status,
                "domain": doc.domain,
                "doc_type": doc.doc_type,
                "provider": provider,
                "provider_name": provider_name,
                "provider_url": provider_url,
                "storage_key": doc.s3_key,
                "mime_type": doc.mime,
            }
        )
        
        # Set status to processing if not already
        if doc.status != "processing":
            doc.status = "processing"
        # Set OCR status to processing using helper
        set_ocr_status(doc, PipelineStepStatus.PROCESSING, reason="OCR task started")
        update_document(db, doc)
        db.commit()
    except Exception as e:
        error_msg = f"Failed to initialize OCR: {str(e)}"
        logger.error(
            "OCR initialization failed",
            extra={
                "event": "ocr.init_failure",
                "request_id": request_id,
                "document_id": document_id,
                "error": error_msg,
                "error_type": type(e).__name__,
            },
            exc_info=True
        )
        try:
            extracted_data = doc.extracted or {}
            extracted_data["ocr_error"] = error_msg
            doc.extracted = extracted_data
            set_ocr_status(doc, PipelineStepStatus.ERROR, reason=error_msg)
            update_document(db, doc)
            db.commit()
        except Exception:
            pass
        return {"success": False, "document_id": document_id, "step": "ocr", "error": error_msg}
    
    # Step 2: Extract text (skip OCR for text/plain, read directly)
    ocr_result = None
    try:
        if doc.mime == "text/plain":
            # Skip OCR for text files, read directly from storage
            logger.info(
                "Skipping OCR for text/plain, reading directly from storage",
                extra={
                    "event": "ocr.text_skip",
                    "request_id": request_id,
                    "document_id": document_id,
                    "storage_key": doc.s3_key,
                }
            )
            
            try:
                text_content = read_text_file(doc.s3_key)
                # Create OcrResult-like object
                ocr_result = OcrResult(
                    text=text_content,
                    page_count=1,
                    language="en"
                )
                logger.info(
                    "Text file read successfully",
                    extra={
                        "event": "ocr.text_read_success",
                        "request_id": request_id,
                        "document_id": document_id,
                        "text_length": len(text_content),
                    }
                )
            except FileNotFoundError as e:
                error_msg = f"File not found in storage: {str(e)}"
                logger.error(
                    "Text file not found",
                    extra={
                        "event": "ocr.text_read_not_found",
                        "request_id": request_id,
                        "document_id": document_id,
                        "storage_key": doc.s3_key,
                        "error": error_msg,
                    }
                )
                raise
            except Exception as e:
                error_msg = f"Failed to read text file: {str(e)}"
                logger.error(
                    "Text file read failed",
                    extra={
                        "event": "ocr.text_read_failure",
                        "request_id": request_id,
                        "document_id": document_id,
                        "storage_key": doc.s3_key,
                        "error": error_msg,
                        "error_type": type(e).__name__,
                    },
                    exc_info=True
                )
                raise
        else:
            # Call OCR service for PDF/images
            try:
                ocr_result = ocr_service.extract_document(
                    storage_key=doc.s3_key,
                    mime_type=doc.mime,
                    request_id=request_id,  # Forward request_id to OCR service
                )
                logger.info(
                    "OCR extraction completed",
                    extra={
                        "event": "ocr.finish",
                        "request_id": request_id,
                        "document_id": str(document_id),
                        "page_count": ocr_result.page_count if ocr_result else None,
                        "language": ocr_result.language if ocr_result else None,
                        "text_length": len(ocr_result.text) if ocr_result else 0,
                        "ocr_chars": len(ocr_result.text) if ocr_result else 0,
                    }
                )
            except Exception as e:
                error_msg = f"OCR extraction failed: {str(e)}"
                # Log with provider URL and response details if available
                log_extra = {
                    "event": "ocr.fail",
                    "request_id": request_id,
                    "document_id": str(document_id),
                    "provider": provider,
                    "provider_url": provider_url,
                    "error": error_msg,
                    "error_type": type(e).__name__,
                }
                # Try to extract response details from HTTP errors
                if hasattr(e, 'response'):
                    if hasattr(e.response, 'status_code'):
                        log_extra["response_status"] = e.response.status_code
                    if hasattr(e.response, 'text'):
                        response_text = e.response.text[:500]  # Truncate to 500 chars
                        log_extra["response_body"] = response_text
                logger.error("OCR extraction failed", extra=log_extra, exc_info=True)
                raise
    except Exception as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        error_msg = str(e)
        
        # Store error in extracted field
        try:
            extracted_data = doc.extracted or {}
            extracted_data["ocr_error"] = error_msg
            doc.extracted = extracted_data
            set_ocr_status(doc, PipelineStepStatus.ERROR, reason=error_msg)
            db.commit()
        except Exception as db_err:
            logger.error(
                "Failed to save OCR error to database",
                extra={
                    "request_id": request_id,
                    "document_id": document_id,
                    "db_error": str(db_err),
                },
                exc_info=True
            )
        
        return {
            "success": False,
            "document_id": document_id,
            "step": "ocr",
            "error": error_msg,
            "duration_ms": round(duration_ms, 2),
        }
    
    # Step 3: Update document with OCR results
    try:
        # Update document with OCR results
        # Store full OCR text in body and extracted
        full_ocr_text = ocr_result.text
        doc.body = full_ocr_text
        
        # Store OCR character count (CHUNK 2: cost hints)
        doc.ocr_chars = len(full_ocr_text)
        
        # Ensure extracted["text"] is also set for consistency
        extracted_data = doc.extracted or {}
        extracted_data["text"] = full_ocr_text
        extracted_data["ocr"] = {
            "page_count": ocr_result.page_count,
            "language": ocr_result.language,
            "provider": provider,
            "provider_name": provider_name,
        }
        # Clear any previous error
        extracted_data.pop("ocr_error", None)
        doc.extracted = extracted_data
        
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
        
        # Update status to ready
        doc.status = "ready"
        set_ocr_status(doc, PipelineStepStatus.READY, reason="OCR completed successfully")
        
        # Set llm_status to ready when OCR completes (chat is now available)
        # This ensures llm_status doesn't remain "pending" when chat is available
        # Note: llm_status="ready" here means "chat available", not "LLM analysis complete"
        # The LLM analysis task will still run and update extracted fields, but chat works immediately
        from app.services.status import set_llm_status
        if doc.llm_status == PipelineStepStatus.PENDING.value:
            set_llm_status(doc, PipelineStepStatus.READY, reason="OCR completed - chat now available")
            logger.info(
                "LLM status set to ready (chat available)",
                extra={
                    "event": "ocr.llm_status_ready",
                    "request_id": request_id,
                    "document_id": document_id,
                    "reason": "OCR completed - chat now available",
                }
            )
        
        # Explicitly update document in Firestore (SQLAlchemy tracks changes automatically)
        # Log backend type once per processing request
        from app.infrastructure.db.db_helpers import is_firestore_adapter
        if is_firestore_adapter(db):
            logger.info(
                "Updating document in Firestore",
                extra={
                    "event": "ocr.firestore_update",
                    "request_id": request_id,
                    "document_id": document_id,
                    "body_length": len(doc.body),
                    "ocr_status": doc.ocr_status,
                }
            )
        update_document(db, doc)
        db.commit()
    except Exception as e:
        error_msg = f"Failed to update document with OCR results: {str(e)}"
        logger.error(
            "Failed to update document after OCR",
            extra={
                "event": "ocr.update_failure",
                "request_id": request_id,
                "document_id": document_id,
                "error": error_msg,
                "error_type": type(e).__name__,
            },
            exc_info=True
        )
        try:
            extracted_data = doc.extracted or {}
            extracted_data["ocr_error"] = error_msg
            doc.extracted = extracted_data
            set_ocr_status(doc, PipelineStepStatus.ERROR, reason=error_msg)
            update_document(db, doc)
            db.commit()
        except Exception:
            pass
        
        duration_ms = (time.monotonic() - start_time) * 1000
        return {
            "success": False,
            "document_id": document_id,
            "step": "ocr",
            "error": error_msg,
            "duration_ms": round(duration_ms, 2),
        }
    
    duration_ms = (time.monotonic() - start_time) * 1000
    
    logger.info(
        "OCR processing completed successfully",
        extra={
            "event": "ocr.finish",
            "request_id": request_id,
            "document_id": str(document_id),
            "status": doc.status,
            "ocr_status": doc.ocr_status,
            "page_count": ocr_result.page_count,
            "language": ocr_result.language,
            "domain": doc.domain,
            "doc_type": doc.doc_type,
            "provider": provider,
            "provider_name": provider_name,
            "text_length": len(ocr_result.text),
            "ocr_chars": len(ocr_result.text),
            "duration_ms": round(duration_ms, 2),
        }
    )
    
    return {
        "success": True,
        "document_id": document_id,
        "step": "ocr",
        "page_count": ocr_result.page_count,
        "language": ocr_result.language,
        "duration_ms": round(duration_ms, 2),
    }


def process_document_llm_sync(doc: Document, db) -> dict:
    """Process LLM analysis for a document synchronously (shared logic for Celery and HTTP).
    
    Args:
        doc: Document instance
        db: Database session/adapter
        
    Returns:
        Dict with success status and metadata (never raises, always returns)
    """
    start_time = time.monotonic()
    document_id = doc.id
    request_id = doc.request_id if hasattr(doc, 'request_id') else None
    
    # Step 1: Validate document is ready
    try:
        # Check for text in doc.body OR extracted.get("text") for consistency
        has_text = bool(doc.body) or bool(doc.extracted and doc.extracted.get("text"))
        is_ready = doc.status == "ready" or doc.ocr_status == PipelineStepStatus.READY.value
        
        if not has_text or not is_ready:
            error_msg = f"Document not ready for LLM analysis (status: {doc.status}, ocr_status: {doc.ocr_status}, has_body: {bool(doc.body)}, has_extracted_text: {bool(doc.extracted and doc.extracted.get('text'))})"
            logger.warning(
                "Document not ready for LLM analysis",
                extra={
                    "event": "llm.not_ready",
                    "request_id": request_id,
                    "document_id": document_id,
                    "status": doc.status,
                    "ocr_status": doc.ocr_status,
                    "has_body": bool(doc.body),
                    "has_extracted_text": bool(doc.extracted and doc.extracted.get("text")),
                }
            )
            # Set LLM status to error since we can't proceed
            try:
                extracted_data = doc.extracted or {}
                extracted_data["llm_error"] = error_msg
                doc.extracted = extracted_data
                set_llm_status(doc, PipelineStepStatus.ERROR, reason=error_msg)
                update_document(db, doc)
                db.commit()
            except Exception:
                pass
            return {"success": False, "document_id": document_id, "step": "llm", "error": error_msg}
        
        # Use doc.body if available, otherwise fall back to extracted.get("text")
        if not doc.body and doc.extracted and doc.extracted.get("text"):
            doc.body = doc.extracted.get("text")
            logger.info(
                "Using extracted text from extracted field",
                extra={
                    "event": "llm.text_fallback",
                    "request_id": request_id,
                    "document_id": document_id,
                    "text_length": len(doc.body),
                }
            )
    except Exception as e:
        error_msg = f"Failed to validate document readiness: {str(e)}"
        logger.error(
            "Document validation failed",
            extra={
                "event": "llm.validation_failure",
                "request_id": request_id,
                "document_id": document_id,
                "error": error_msg,
                "error_type": type(e).__name__,
            },
            exc_info=True
        )
        try:
            extracted_data = doc.extracted or {}
            extracted_data["llm_error"] = error_msg
            doc.extracted = extracted_data
            set_llm_status(doc, PipelineStepStatus.ERROR, reason=error_msg)
            db.commit()
        except Exception:
            pass
        return {"success": False, "document_id": document_id, "step": "llm", "error": error_msg}
    
    # Step 2: Initialize LLM service
    try:
        # Get LLM service to determine provider
        llm_service = get_llm_service()
        provider = settings.LLM_PROVIDER or "fake"
        provider_name = type(llm_service).__name__
        provider_url = getattr(llm_service, 'base_url', None) if hasattr(llm_service, 'base_url') else None
        
        logger.info(
            "LLM analysis started",
            extra={
                "event": "llm.start",
                "request_id": request_id,
                "document_id": str(document_id),
                "domain": doc.domain,
                "doc_type": doc.doc_type,
                "text_length": len(ocr_text_full),
                "sent_chars": llm_chars_sent,
                "ocr_status": doc.ocr_status,
                "llm_status": doc.llm_status,
                "provider": provider,
                "provider_name": provider_name,
                "provider_url": provider_url,
                "mime_type": doc.mime,
            }
        )
        
        # Set LLM status to processing using helper
        # Note: If llm_status is already "ready" (from OCR completion), this will transition to "processing"
        # to indicate LLM analysis is in progress
        set_llm_status(doc, PipelineStepStatus.PROCESSING, reason="LLM task started")
        update_document(db, doc)
        db.commit()
    except Exception as e:
        error_msg = f"Failed to initialize LLM service: {str(e)}"
        logger.error(
            "LLM initialization failed",
            extra={
                "event": "llm.init_failure",
                "request_id": request_id,
                "document_id": document_id,
                "error": error_msg,
                "error_type": type(e).__name__,
            },
            exc_info=True
        )
        try:
            extracted_data = doc.extracted or {}
            extracted_data["llm_error"] = error_msg
            doc.extracted = extracted_data
            set_llm_status(doc, PipelineStepStatus.ERROR, reason=error_msg)
            db.commit()
        except Exception:
            pass
        return {"success": False, "document_id": document_id, "step": "llm", "error": error_msg}
    
    # Step 3: Truncate OCR text before sending to LLM (CHUNK 2: cost guardrails)
    max_ocr_chars = settings.MAX_OCR_CHARS if hasattr(settings, 'MAX_OCR_CHARS') else 50000
    ocr_text_full = doc.body
    ocr_text_truncated = ocr_text_full[:max_ocr_chars] if len(ocr_text_full) > max_ocr_chars else ocr_text_full
    llm_chars_sent = len(ocr_text_truncated)
    
    # Store cost hints
    doc.llm_chars_sent = llm_chars_sent
    
    logger.info(
        "OCR text prepared for LLM",
        extra={
            "event": "llm.text_prepared",
            "request_id": request_id,
            "document_id": document_id,
            "ocr_chars": len(ocr_text_full),
            "sent_chars": llm_chars_sent,
            "truncated": len(ocr_text_full) > max_ocr_chars,
        }
    )
    
    # Step 4: Call LLM service with truncated text
    llm_result = None
    try:
        llm_result = llm_service.analyze_document(
            text=ocr_text_truncated,  # Send truncated text to LLM
            mime_type=doc.mime,
            doc_type=doc.doc_type,
        )
        logger.info(
            "LLM analysis completed",
            extra={
                "event": "llm.analysis_success",
                "request_id": request_id,
                "document_id": document_id,
                "summary_length": len(llm_result.summary) if llm_result else 0,
                "entities_count": len(llm_result.entities) if llm_result else 0,
                "ocr_chars": len(ocr_text_full),
                "llm_chars_sent": llm_chars_sent,
            }
        )
    except Exception as e:
        error_msg = f"LLM analysis failed: {str(e)}"
        # Log with provider URL and response details if available
        log_extra = {
            "event": "llm.analysis_failure",
            "request_id": request_id,
            "document_id": document_id,
            "provider": provider,
            "provider_url": provider_url,
            "error": error_msg,
            "error_type": type(e).__name__,
        }
        # Try to extract response details from HTTP errors
        if hasattr(e, 'response'):
            if hasattr(e.response, 'status_code'):
                log_extra["response_status"] = e.response.status_code
            if hasattr(e.response, 'text'):
                response_text = e.response.text[:500]  # Truncate to 500 chars
                log_extra["response_body"] = response_text
        logger.error("LLM analysis failed", extra=log_extra, exc_info=True)
        
        try:
            extracted_data = doc.extracted or {}
            extracted_data["llm_error"] = error_msg
            doc.extracted = extracted_data
            set_llm_status(doc, PipelineStepStatus.ERROR, reason=error_msg)
            update_document(db, doc)
            db.commit()
        except Exception as db_err:
            logger.error(
                "Failed to save LLM error to database",
                extra={
                    "request_id": request_id,
                    "document_id": document_id,
                    "db_error": str(db_err),
                },
                exc_info=True
            )
        
        duration_ms = (time.monotonic() - start_time) * 1000
        return {
            "success": False,
            "document_id": document_id,
            "step": "llm",
            "error": error_msg,
            "duration_ms": round(duration_ms, 2),
        }
    
    # Step 4: Update document with LLM results
    try:
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
        # Ensure text is preserved in extracted if body exists
        if doc.body and "text" not in extracted_data:
            extracted_data["text"] = doc.body
        # Clear any previous error
        extracted_data.pop("llm_error", None)
        doc.extracted = extracted_data
        
        # Update LLM status to ready
        set_llm_status(doc, PipelineStepStatus.READY, reason="LLM analysis completed successfully")
        
        # Explicitly update document in Firestore (SQLAlchemy tracks changes automatically)
        from app.infrastructure.db.db_helpers import is_firestore_adapter
        if is_firestore_adapter(db):
            logger.info(
                "Updating document in Firestore",
                extra={
                    "event": "llm.firestore_update",
                    "request_id": request_id,
                    "document_id": document_id,
                    "llm_status": doc.llm_status,
                }
            )
        update_document(db, doc)
        db.commit()
    except Exception as e:
        error_msg = f"Failed to update document with LLM results: {str(e)}"
        logger.error(
            "Failed to update document after LLM",
            extra={
                "event": "llm.update_failure",
                "request_id": request_id,
                "document_id": document_id,
                "error": error_msg,
                "error_type": type(e).__name__,
            },
            exc_info=True
        )
        try:
            extracted_data = doc.extracted or {}
            extracted_data["llm_error"] = error_msg
            doc.extracted = extracted_data
            set_llm_status(doc, PipelineStepStatus.ERROR, reason=error_msg)
            update_document(db, doc)
            db.commit()
        except Exception:
            pass
        
        duration_ms = (time.monotonic() - start_time) * 1000
        return {
            "success": False,
            "document_id": document_id,
            "step": "llm",
            "error": error_msg,
            "duration_ms": round(duration_ms, 2),
        }
    
    duration_ms = (time.monotonic() - start_time) * 1000
    
        logger.info(
            "LLM analysis completed successfully",
            extra={
                "event": "llm.finish",
                "request_id": request_id,
                "document_id": str(document_id),
                "domain": doc.domain,
                "doc_type": doc.doc_type,
                "ocr_chars": len(ocr_text_full),
                "llm_chars_sent": llm_chars_sent,
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
        "duration_ms": round(duration_ms, 2),
    }
