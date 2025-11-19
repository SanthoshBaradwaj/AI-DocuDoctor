from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.infrastructure.db.sql_alchemy import get_db
from app.infrastructure.db.models import Document
from app.schemas import ChatRequestIn, ChatResponseOut, ChatMessageIn
from app.infrastructure.ai.base import get_llm_service

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])
logger = get_logger(__name__)


@router.post("/document/{doc_id}", response_model=ChatResponseOut)
def chat_with_document(
    doc_id: int,
    payload: ChatRequestIn,
    request: Request,
    db: Session = Depends(get_db),
):
    """Chat about a specific document.
    
    Fetches the document and uses it as context for the LLM conversation.
    """
    request_id = getattr(request.state, "request_id", None)
    
    logger.info(
        "Document chat request",
        extra={
            "request_id": request_id,
            "doc_id": doc_id,
            "message_count": len(payload.messages),
        }
    )
    
    # Fetch document
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    
    # Build context from document
    context_parts = [f"Document: {doc.title}"]
    if doc.excerpt:
        context_parts.append(f"Excerpt: {doc.excerpt[:200]}")
    if doc.extracted:
        summary = doc.extracted.get("summary", "")
        if summary:
            context_parts.append(f"Summary: {summary}")
    context = " | ".join(context_parts)
    
    # Get the last user message
    user_messages = [m for m in payload.messages if m.role == "user"]
    if not user_messages:
        raise HTTPException(400, "No user message found in request")
    
    last_user_message = user_messages[-1].content
    
    # Get LLM service (abstracted - no direct SDK calls)
    llm_service = get_llm_service()
    
    # Generate response
    reply = llm_service.generate(
        prompt=last_user_message,
        context=context or f"Document ID: {doc_id}"
    )
    
    # Build response with full conversation
    response_messages = list(payload.messages)
    response_messages.append(
        ChatMessageIn(role="assistant", content=reply)
    )
    
    return ChatResponseOut(
        reply=reply,
        messages=response_messages,
    )


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
        "Global chat request",
        extra={
            "request_id": request_id,
            "doc_count": doc_count,
            "domains": domain_list,
            "message_count": len(payload.messages),
        }
    )
    
    context = f"You have {doc_count} document(s)"
    if domain_list:
        context += f" across {len(domain_list)} domain(s): {', '.join(domain_list)}"
    
    # Get the last user message
    user_messages = [m for m in payload.messages if m.role == "user"]
    if not user_messages:
        raise HTTPException(400, "No user message found in request")
    
    last_user_message = user_messages[-1].content
    
    # Get LLM service (abstracted - no direct SDK calls)
    llm_service = get_llm_service()
    
    # Generate response
    reply = llm_service.generate(
        prompt=last_user_message,
        context=context
    )
    
    # Build response with full conversation
    response_messages = list(payload.messages)
    response_messages.append(
        ChatMessageIn(role="assistant", content=reply)
    )
    
    return ChatResponseOut(
        reply=reply,
        messages=response_messages,
    )


# Legacy endpoint (kept for backward compatibility)
@router.post("", response_model=ChatResponseOut)
def chat_legacy(
    payload: ChatRequestIn,
    db: Session = Depends(get_db),
):
    """Legacy chat endpoint - redirects to global chat."""
    return chat_global(payload, db)
