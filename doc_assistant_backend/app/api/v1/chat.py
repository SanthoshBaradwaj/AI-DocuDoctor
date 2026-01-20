import time
import uuid
import json
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import httpx

from app.core.logging import get_logger
from app.core.config import get_settings
from app.infrastructure.db.db_factory import get_db
from app.infrastructure.db.models import Document
from app.infrastructure.db.db_helpers import get_document
from app.schemas import ChatRequestIn, ChatResponseOut, ChatMessageIn
from app.infrastructure.ai.base import get_llm_service

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])
logger = get_logger(__name__)
settings = get_settings()


def normalize_error_response(
    error_code: str,
    message: str,
    details: dict | None = None,
    request_id: str | None = None,
) -> dict:
    """Normalize error response to consistent format.
    
    Args:
        error_code: Error code string
        message: Human-readable error message (always a string)
        details: Optional details object (for upstream errors, etc.)
        request_id: Optional request ID
        
    Returns:
        Normalized error dict
    """
    return {
        "error_code": error_code,
        "message": message,
        "details": details,
        "request_id": request_id,
    }


def extract_upstream_error_details(response: httpx.Response) -> dict | None:
    """Extract error details from upstream service response.
    
    If the upstream service returns a JSON error body, extract it into details.
    
    Args:
        response: HTTP response from upstream service
        
    Returns:
        Dict with error details or None
    """
    try:
        if response.headers.get("content-type", "").startswith("application/json"):
            error_body = response.json()
            if isinstance(error_body, dict):
                # Extract relevant fields from upstream error
                details = {}
                if "error_code" in error_body:
                    details["upstream_error_code"] = error_body["error_code"]
                if "message" in error_body:
                    details["upstream_message"] = error_body["message"]
                if "details" in error_body:
                    details["upstream_details"] = error_body["details"]
                # Include full error body if it's not too large
                if len(json.dumps(error_body)) < 1000:
                    details["upstream_response"] = error_body
                return details if details else None
    except (json.JSONDecodeError, ValueError, TypeError):
        # If we can't parse JSON, return None
        pass
    return None


@router.post("/document/{doc_id}", response_model=ChatResponseOut)
def chat_with_document(
    doc_id: str,
    payload: ChatRequestIn,
    request: Request,
    db: Session = Depends(get_db),
):
    """Chat about a specific document.
    
    Fetches the document and uses it as context for the LLM conversation.
    """
    request_id = getattr(request.state, "request_id", None)
    if not request_id:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
    
    start_time = time.time()
    
    logger.info(
        "Document chat request started",
        extra={
            "request_id": request_id,
            "doc_id": doc_id,
            "message_count": len(payload.messages),
        }
    )
    
    try:
        # Fetch document
        doc = get_document(db, doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Build context from document
        context_parts = [f"Document: {doc.title}"]
        if doc.excerpt:
            context_parts.append(f"Excerpt: {doc.excerpt[:200]}")
        if doc.extracted:
            summary = doc.extracted.get("summary", "")
            if summary:
                context_parts.append(f"Summary: {summary}")
            # Also include extracted.text and body if available
            extracted_text = doc.extracted.get("text", "")
            if extracted_text:
                context_parts.append(f"Content: {extracted_text[:1000]}")  # Limit context length
        context = " | ".join(context_parts)
        
        # Get the last user message
        user_messages = [m for m in payload.messages if m.role == "user"]
        if not user_messages:
            raise HTTPException(status_code=400, detail="No user message found in request")
        
        last_user_message = user_messages[-1].content
        
        # Get LLM service (abstracted - no direct SDK calls)
        llm_service = get_llm_service()
        
        # Generate response with error handling
        try:
            reply = llm_service.generate(
                prompt=last_user_message,
                context=context or f"Document ID: {doc_id}",
                request_id=request_id
            )
        except httpx.TimeoutException as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "LLM service timeout during chat",
                extra={
                    "request_id": request_id,
                    "doc_id": doc_id,
                    "duration_ms": round(duration_ms, 2),
                    "error_type": "LLM_TIMEOUT",
                },
                exc_info=True
            )
            error_response = normalize_error_response(
                error_code="LLM_TIMEOUT",
                message="LLM service timed out",
                details={"doc_id": doc_id},
                request_id=request_id,
            )
            raise HTTPException(status_code=504, detail=error_response)
        except (httpx.ConnectError, httpx.NetworkError) as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "LLM service unreachable during chat",
                extra={
                    "request_id": request_id,
                    "doc_id": doc_id,
                    "duration_ms": round(duration_ms, 2),
                    "error_type": "LLM_UNREACHABLE",
                },
                exc_info=True
            )
            error_response = normalize_error_response(
                error_code="LLM_UNREACHABLE",
                message="LLM service is unreachable",
                details={"doc_id": doc_id},
                request_id=request_id,
            )
            raise HTTPException(status_code=502, detail=error_response)
        except httpx.HTTPStatusError as e:
            duration_ms = (time.time() - start_time) * 1000
            # Map upstream 4xx/5xx to 502
            error_code = "LLM_UPSTREAM_ERROR"
            
            # Extract upstream error details if available
            upstream_details = extract_upstream_error_details(e.response)
            details = {"doc_id": doc_id}
            if upstream_details:
                details.update(upstream_details)
            
            logger.error(
                "LLM service returned error status during chat",
                extra={
                    "request_id": request_id,
                    "doc_id": doc_id,
                    "upstream_status_code": e.response.status_code,
                    "duration_ms": round(duration_ms, 2),
                    "error_type": error_code,
                },
                exc_info=True
            )
            error_response = normalize_error_response(
                error_code=error_code,
                message=f"LLM service returned error: {e.response.status_code}",
                details=details,
                request_id=request_id,
            )
            raise HTTPException(status_code=502, detail=error_response)
        except (ValueError, TypeError, KeyError) as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "Invalid LLM service response during chat",
                extra={
                    "request_id": request_id,
                    "doc_id": doc_id,
                    "duration_ms": round(duration_ms, 2),
                    "error_type": "LLM_BAD_RESPONSE",
                    "error": str(e),
                },
                exc_info=True
            )
            error_response = normalize_error_response(
                error_code="LLM_BAD_RESPONSE",
                message="LLM service returned invalid response",
                details={"doc_id": doc_id, "error": str(e)},
                request_id=request_id,
            )
            raise HTTPException(status_code=502, detail=error_response)
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "Unexpected error calling LLM service during chat",
                extra={
                    "request_id": request_id,
                    "doc_id": doc_id,
                    "duration_ms": round(duration_ms, 2),
                    "error_type": type(e).__name__,
                },
                exc_info=True
            )
            # Re-raise as 502 for upstream errors
            error_response = normalize_error_response(
                error_code="LLM_UPSTREAM_ERROR",
                message="LLM service error",
                details={"doc_id": doc_id},
                request_id=request_id,
            )
            raise HTTPException(status_code=502, detail=error_response)
        
        # Check reply length guardrails
        if len(reply) > settings.MAX_REPLY_CHARS:
            duration_ms = (time.time() - start_time) * 1000
            logger.warning(
                "Reply length exceeds maximum",
                extra={
                    "request_id": request_id,
                    "doc_id": doc_id,
                    "reply_length": len(reply),
                    "max_reply_chars": settings.MAX_REPLY_CHARS,
                    "duration_ms": round(duration_ms, 2),
                }
            )
            error_response = normalize_error_response(
                error_code="REPLY_TOO_LONG",
                message=f"Reply length ({len(reply)} chars) exceeds maximum ({settings.MAX_REPLY_CHARS} chars)",
                details={"doc_id": doc_id, "reply_length": len(reply), "max_reply_chars": settings.MAX_REPLY_CHARS},
                request_id=request_id,
            )
            raise HTTPException(status_code=413, detail=error_response)
        
        # Build response with full conversation
        response_messages = list(payload.messages)
        response_messages.append(
            ChatMessageIn(role="assistant", content=reply)
        )
        
        duration_ms = (time.time() - start_time) * 1000
        
        logger.info(
            "Document chat request completed",
            extra={
                "request_id": request_id,
                "doc_id": doc_id,
                "duration_ms": round(duration_ms, 2),
            }
        )
        
        return ChatResponseOut(
            reply=reply,
            messages=response_messages,
        )
    except HTTPException:
        # Re-raise HTTPExceptions as-is (they already have proper status codes)
        raise
    except Exception as e:
        # Catch any other unexpected errors
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            "Unexpected error in chat endpoint",
            extra={
                "request_id": request_id,
                "doc_id": doc_id,
                "duration_ms": round(duration_ms, 2),
                "error_type": type(e).__name__,
            },
            exc_info=True
        )
        # Let the global exception handler catch this
        raise


@router.post("/global", response_model=ChatResponseOut)
def chat_global(
    payload: ChatRequestIn,
    request: Request,
    db: Session = Depends(get_db),
):
    """Global chat across all user documents.
    
    For now, builds a simple placeholder context. Later, this will:
    - Load all relevant documents for the user
    - Summarize them
    - Use them as context for multi-doc conversation
    """
    request_id = getattr(request.state, "request_id", None)
    if not request_id:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
    
    start_time = time.time()
    
    # For now, build simple placeholder context
    # TODO: Load and summarize all user documents
    doc_count = db.query(Document).filter(Document.owner_id == 1).count()
    
    # Simple domain breakdown (placeholder)
    domains = db.query(Document.domain).filter(
        Document.owner_id == 1,
        Document.domain.isnot(None)
    ).distinct().all()
    domain_list = [d[0] for d in domains if d[0]]
    
    logger.info(
        "Global chat request started",
        extra={
            "request_id": request_id,
            "doc_count": doc_count,
            "domains": domain_list,
            "message_count": len(payload.messages),
        }
    )
    
    try:
        context = f"You have {doc_count} document(s)"
        if domain_list:
            context += f" across {len(domain_list)} domain(s): {', '.join(domain_list)}"
        
        # Get the last user message
        user_messages = [m for m in payload.messages if m.role == "user"]
        if not user_messages:
            raise HTTPException(status_code=400, detail="No user message found in request")
        
        last_user_message = user_messages[-1].content
        
        # Get LLM service (abstracted - no direct SDK calls)
        llm_service = get_llm_service()
        
        # Generate response with error handling
        try:
            reply = llm_service.generate(
                prompt=last_user_message,
                context=context,
                request_id=request_id
            )
        except httpx.TimeoutException as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "LLM service timeout during global chat",
                extra={
                    "request_id": request_id,
                    "duration_ms": round(duration_ms, 2),
                    "error_type": "LLM_TIMEOUT",
                },
                exc_info=True
            )
            error_response = normalize_error_response(
                error_code="LLM_TIMEOUT",
                message="LLM service timed out",
                details={},
                request_id=request_id,
            )
            raise HTTPException(status_code=504, detail=error_response)
        except (httpx.ConnectError, httpx.NetworkError) as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "LLM service unreachable during global chat",
                extra={
                    "request_id": request_id,
                    "duration_ms": round(duration_ms, 2),
                    "error_type": "LLM_UNREACHABLE",
                },
                exc_info=True
            )
            error_response = normalize_error_response(
                error_code="LLM_UNREACHABLE",
                message="LLM service is unreachable",
                details={},
                request_id=request_id,
            )
            raise HTTPException(status_code=502, detail=error_response)
        except httpx.HTTPStatusError as e:
            duration_ms = (time.time() - start_time) * 1000
            error_code = "LLM_UPSTREAM_ERROR"
            
            # Extract upstream error details if available
            upstream_details = extract_upstream_error_details(e.response)
            details = upstream_details if upstream_details else {}
            
            logger.error(
                "LLM service returned error status during global chat",
                extra={
                    "request_id": request_id,
                    "upstream_status_code": e.response.status_code,
                    "duration_ms": round(duration_ms, 2),
                    "error_type": error_code,
                },
                exc_info=True
            )
            error_response = normalize_error_response(
                error_code=error_code,
                message=f"LLM service returned error: {e.response.status_code}",
                details=details,
                request_id=request_id,
            )
            raise HTTPException(status_code=502, detail=error_response)
        except (ValueError, TypeError, KeyError) as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "Invalid LLM service response during global chat",
                extra={
                    "request_id": request_id,
                    "duration_ms": round(duration_ms, 2),
                    "error_type": "LLM_BAD_RESPONSE",
                    "error": str(e),
                },
                exc_info=True
            )
            error_response = normalize_error_response(
                error_code="LLM_BAD_RESPONSE",
                message="LLM service returned invalid response",
                details={"error": str(e)},
                request_id=request_id,
            )
            raise HTTPException(status_code=502, detail=error_response)
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "Unexpected error calling LLM service during global chat",
                extra={
                    "request_id": request_id,
                    "duration_ms": round(duration_ms, 2),
                    "error_type": type(e).__name__,
                },
                exc_info=True
            )
            error_response = normalize_error_response(
                error_code="LLM_UPSTREAM_ERROR",
                message="LLM service error",
                details={},
                request_id=request_id,
            )
            raise HTTPException(status_code=502, detail=error_response)
        
        # Check reply length guardrails
        if len(reply) > settings.MAX_REPLY_CHARS:
            duration_ms = (time.time() - start_time) * 1000
            logger.warning(
                "Reply length exceeds maximum",
                extra={
                    "request_id": request_id,
                    "reply_length": len(reply),
                    "max_reply_chars": settings.MAX_REPLY_CHARS,
                    "duration_ms": round(duration_ms, 2),
                }
            )
            error_response = normalize_error_response(
                error_code="REPLY_TOO_LONG",
                message=f"Reply length ({len(reply)} chars) exceeds maximum ({settings.MAX_REPLY_CHARS} chars)",
                details={"reply_length": len(reply), "max_reply_chars": settings.MAX_REPLY_CHARS},
                request_id=request_id,
            )
            raise HTTPException(status_code=413, detail=error_response)
        
        # Build response with full conversation
        response_messages = list(payload.messages)
        response_messages.append(
            ChatMessageIn(role="assistant", content=reply)
        )
        
        duration_ms = (time.time() - start_time) * 1000
        
        logger.info(
            "Global chat request completed",
            extra={
                "request_id": request_id,
                "duration_ms": round(duration_ms, 2),
            }
        )
        
        return ChatResponseOut(
            reply=reply,
            messages=response_messages,
        )
    except HTTPException:
        # Re-raise HTTPExceptions as-is (they already have proper status codes)
        raise
    except Exception as e:
        # Catch any other unexpected errors
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            "Unexpected error in global chat endpoint",
            extra={
                "request_id": request_id,
                "duration_ms": round(duration_ms, 2),
                "error_type": type(e).__name__,
            },
            exc_info=True
        )
        # Let the global exception handler catch this
        raise


# Legacy endpoint (kept for backward compatibility)
@router.post("", response_model=ChatResponseOut)
def chat_legacy(
    payload: ChatRequestIn,
    request: Request,
    db: Session = Depends(get_db),
):
    """Legacy chat endpoint - redirects to global chat."""
    return chat_global(payload, request, db)
