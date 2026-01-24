"""Status transition helpers for document processing pipeline."""
from app.infrastructure.db.models import Document
from app.core.constants import PipelineStepStatus
from app.core.logging import get_logger

logger = get_logger(__name__)


def set_ocr_status(doc: Document, new_status: PipelineStepStatus, *, reason: str | None = None) -> None:
    """Set OCR status with validation of allowed transitions.
    
    Allowed transitions:
    - pending -> processing
    - processing -> ready/error
    - error -> pending (reprocessing)
    - ready -> pending (reprocessing)
    
    Args:
        doc: Document instance
        new_status: New OCR status
        reason: Optional reason for the transition (for logging)
    """
    current = PipelineStepStatus(doc.ocr_status) if doc.ocr_status else PipelineStepStatus.PENDING
    
    # Define allowed transitions
    allowed_transitions = {
        PipelineStepStatus.PENDING: {PipelineStepStatus.PROCESSING},
        PipelineStepStatus.PROCESSING: {PipelineStepStatus.READY, PipelineStepStatus.ERROR},
        PipelineStepStatus.ERROR: {PipelineStepStatus.PENDING},  # Reprocessing
        PipelineStepStatus.READY: {PipelineStepStatus.PENDING},  # Reprocessing
    }
    
    if new_status not in allowed_transitions.get(current, set()):
        logger.warning(
            "Unexpected OCR status transition",
            extra={
                "document_id": doc.id,
                "current_status": current.value,
                "new_status": new_status.value,
                "reason": reason,
            }
        )
        # Still allow the transition, but log it for visibility
    
    doc.ocr_status = new_status.value


def set_llm_status(doc: Document, new_status: PipelineStepStatus, *, reason: str | None = None) -> None:
    """Set LLM status with validation of allowed transitions.
    
    Allowed transitions:
    - pending -> ready (when OCR completes, chat becomes available)
    - pending -> processing (when LLM analysis task starts)
    - processing -> ready/error
    - error -> pending (reprocessing)
    - ready -> pending (reprocessing)
    
    Note: llm_status="ready" can mean either:
    - "chat available" (set when OCR completes)
    - "LLM analysis complete" (set when LLM analysis finishes)
    
    Args:
        doc: Document instance
        new_status: New LLM status
        reason: Optional reason for the transition (for logging)
    """
    current = PipelineStepStatus(doc.llm_status) if doc.llm_status else PipelineStepStatus.PENDING
    
    # Define allowed transitions
    allowed_transitions = {
        PipelineStepStatus.PENDING: {
            PipelineStepStatus.PROCESSING,  # LLM analysis task starts
            PipelineStepStatus.READY,  # OCR completes, chat available
        },
        PipelineStepStatus.PROCESSING: {PipelineStepStatus.READY, PipelineStepStatus.ERROR},
        PipelineStepStatus.ERROR: {PipelineStepStatus.PENDING},  # Reprocessing
        PipelineStepStatus.READY: {
            PipelineStepStatus.PENDING,  # Reprocessing
            PipelineStepStatus.PROCESSING,  # LLM analysis starts (even if already ready from OCR)
        },
    }
    
    if new_status not in allowed_transitions.get(current, set()):
        logger.warning(
            "Unexpected LLM status transition",
            extra={
                "document_id": doc.id,
                "current_status": current.value,
                "new_status": new_status.value,
                "reason": reason,
            }
        )
        # Still allow the transition, but log it for visibility
    
    doc.llm_status = new_status.value

