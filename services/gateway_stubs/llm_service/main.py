"""LLM Gateway Service Stub - Local development stub for LLM analysis."""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="LLM Gateway Service Stub")


class AnalyzeRequest(BaseModel):
    """Request model for LLM analysis."""
    text: str
    mime_type: Optional[str] = None
    doc_type: Optional[str] = None


class AnalyzeResponse(BaseModel):
    """Response model for LLM analysis."""
    summary: str
    entities: List[Dict] = []


def count_tokens(text: str) -> int:
    """Approximate token count by splitting on whitespace."""
    return len(text.split())


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_document(request: AnalyzeRequest):
    """Analyze a document and extract summary and entities.
    
    This is a stub service that generates deterministic results
    for local development.
    """
    text = request.text
    mime_type = request.mime_type
    doc_type = request.doc_type
    
    # Validate input
    if not text or not text.strip():
        raise HTTPException(
            status_code=400,
            detail="Text is required and cannot be empty"
        )
    
    # Generate deterministic summary (first 240 chars + suffix)
    summary = text[:240].strip()
    if len(text) > 240:
        summary += " [stub summary]"
    
    # Generate deterministic entities
    entities = []
    
    # TOKEN_COUNT entity
    token_count = count_tokens(text)
    entities.append({
        "type": "TOKEN_COUNT",
        "value": token_count
    })
    
    # DOC_TYPE entity (if provided)
    if doc_type:
        entities.append({
            "type": "DOC_TYPE",
            "value": doc_type
        })
    
    # FAKE_TAG entity
    entities.append({
        "type": "FAKE_TAG",
        "value": "stub_llm_service"
    })
    
    logger.info(
        "LLM analysis completed",
        extra={
            "text_length": len(text),
            "summary_length": len(summary),
            "entities_count": len(entities),
            "token_count": token_count,
            "doc_type": doc_type,
            "mime_type": mime_type,
        }
    )
    
    return AnalyzeResponse(
        summary=summary,
        entities=entities
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8082)

