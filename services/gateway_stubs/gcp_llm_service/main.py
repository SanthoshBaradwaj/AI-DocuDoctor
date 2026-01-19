"""GCP Gemini LLM Gateway Service - Cloud Run deployable LLM service using Vertex AI Gemini."""
import os
import json
import time
import logging
import re
import asyncio
from typing import Optional, List, Dict, Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel
from google.api_core import exceptions as gcp_exceptions
import google.auth

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="GCP Gemini LLM Gateway Service")

# Configuration from environment
GCP_REGION = os.getenv("GCP_REGION", "us-central1")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-1.5-flash")
MAX_CHARS = int(os.getenv("MAX_CHARS", "50000"))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "15"))

# Initialize Vertex AI (uses ADC)
# Note: GenerativeModel can work without explicit init, but we set region explicitly
try:
    # Try to get project from ADC
    _, project = google.auth.default()
    if project:
        aiplatform.init(project=project, location=GCP_REGION)
        logger.info(f"Vertex AI initialized for project={project}, region={GCP_REGION}")
    else:
        # Fallback: init without project (will use ADC project on first call)
        aiplatform.init(project=None, location=GCP_REGION)
        logger.info(f"Vertex AI initialized for region={GCP_REGION} (project from ADC)")
except Exception as e:
    # Non-fatal: GenerativeModel will use ADC directly if init fails
    logger.warning(f"Vertex AI initialization warning (non-fatal): {e}")


class AnalyzeRequest(BaseModel):
    """Request model for LLM analysis."""
    text: str
    mime_type: Optional[str] = None
    doc_type: Optional[str] = None


class AnalyzeResponse(BaseModel):
    """Response model for LLM analysis."""
    summary: str
    entities: List[Dict[str, Any]] = []


def count_tokens_approx(text: str) -> int:
    """Approximate token count by splitting on whitespace."""
    return len(text.split())


def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Extract JSON object from text, handling markdown code blocks and plain JSON.
    
    Args:
        text: Text that may contain JSON
        
    Returns:
        Parsed JSON dict or None if parsing fails
    """
    # Try to find JSON in markdown code blocks
    json_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
    match = re.search(json_block_pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Try to find JSON object directly
    json_pattern = r'\{.*\}'
    match = re.search(json_pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    
    # Try parsing the entire text as JSON
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    
    return None


def build_prompt(text: str, doc_type: Optional[str] = None) -> str:
    """Build the prompt for Gemini to analyze the document.
    
    Args:
        text: Document text to analyze
        doc_type: Optional document type hint
        
    Returns:
        Formatted prompt string
    """
    doc_type_hint = ""
    if doc_type:
        doc_type_hint = f"\nNote: This document is of type: {doc_type}"
    
    prompt = f"""Analyze the following document and provide a JSON response with:
1. A concise summary (2-3 sentences)
2. A list of entities extracted from the document

{doc_type_hint}

Document text:
{text}

Please respond with a JSON object in this exact format:
{{
  "summary": "Brief summary of the document content",
  "entities": [
    {{"type": "ENTITY_TYPE", "value": "entity_value"}},
    ...
  ]
}}

Extract relevant entities such as dates, names, amounts, locations, document numbers, etc. Be specific and accurate."""
    
    return prompt


async def call_gemini_async(text: str, doc_type: Optional[str] = None) -> Dict[str, Any]:
    """Call Vertex AI Gemini to analyze the document (async wrapper for timeout handling).
    
    Args:
        text: Document text to analyze
        doc_type: Optional document type hint
        
    Returns:
        Dict with 'summary' and 'entities' keys
        
    Raises:
        TimeoutError: If request times out
        RuntimeError: If Vertex AI call fails
    """
    def _call_gemini_sync():
        """Synchronous Gemini call."""
        # Build prompt
        prompt = build_prompt(text, doc_type)
        
        # Initialize model
        model = GenerativeModel(MODEL_NAME)
        
        # Generate content
        generation_config = {
            "temperature": 0.1,
            "max_output_tokens": 2048,
        }
        
        logger.debug(
            "Calling Vertex AI Gemini",
            extra={
                "event": "gcp_llm.gemini.call_started",
                "model_name": MODEL_NAME,
                "text_length": len(text),
                "doc_type": doc_type,
            }
        )
        
        # Call Gemini (synchronous)
        response = model.generate_content(
            prompt,
            generation_config=generation_config,
        )
        
        if not response or not response.text:
            raise RuntimeError("Empty response from Gemini")
        
        return response.text.strip()
    
    start_time = time.time()
    
    try:
        # Run in executor with timeout
        loop = asyncio.get_event_loop()
        response_text = await asyncio.wait_for(
            loop.run_in_executor(None, _call_gemini_sync),
            timeout=REQUEST_TIMEOUT_SECONDS
        )
        
        duration_ms = (time.time() - start_time) * 1000
        
        logger.debug(
            "Gemini response received",
            extra={
                "event": "gcp_llm.gemini.call_completed",
                "response_length": len(response_text),
                "duration_ms": round(duration_ms, 2),
            }
        )
        
        # Try to parse JSON from response
        parsed_json = extract_json_from_text(response_text)
        
        if parsed_json:
            # Validate structure
            summary = parsed_json.get("summary", "")
            entities = parsed_json.get("entities", [])
            
            if not isinstance(entities, list):
                entities = []
            
            # Ensure entities are dicts with type and value
            normalized_entities = []
            for entity in entities:
                if isinstance(entity, dict) and "type" in entity and "value" in entity:
                    normalized_entities.append({
                        "type": str(entity["type"]),
                        "value": entity["value"]
                    })
            
            return {
                "summary": str(summary) if summary else response_text[:500],
                "entities": normalized_entities
            }
        else:
            # Fallback: use response text as summary, minimal entities
            logger.warning(
                "Failed to parse JSON from Gemini response, using fallback",
                extra={
                    "event": "gcp_llm.gemini.json_parse_failed",
                    "response_preview": response_text[:200],
                }
            )
            return {
                "summary": response_text[:2000],  # Limit fallback summary length
                "entities": []
            }
            
    except asyncio.TimeoutError:
        raise TimeoutError(f"Gemini request timed out after {REQUEST_TIMEOUT_SECONDS} seconds")
    except gcp_exceptions.DeadlineExceeded:
        raise TimeoutError(f"Gemini request timed out after {REQUEST_TIMEOUT_SECONDS} seconds")
    except gcp_exceptions.GoogleAPIError as e:
        raise RuntimeError(f"Vertex AI API error: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error calling Gemini: {str(e)}")


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_document(
    request: AnalyzeRequest,
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID")
):
    """Analyze a document using Vertex AI Gemini and extract summary and entities.
    
    Request body:
    - text (required): Document text to analyze
    - mime_type (optional): MIME type of the document
    - doc_type (optional): Document type hint (e.g., "PASSPORT", "BANK_STATEMENT")
    
    Response:
    - summary: Concise summary of the document
    - entities: List of extracted entities with type and value
    """
    start_time = time.time()
    request_id = x_request_id or str(uuid4())
    
    text = request.text
    mime_type = request.mime_type
    doc_type = request.doc_type
    
    # Validate input
    if not text or not text.strip():
        logger.warning(
            "Empty text in analyze request",
            extra={
                "event": "gcp_llm.analyze.validation_failed",
                "request_id": request_id,
            }
        )
        raise HTTPException(
            status_code=400,
            detail="Text is required and cannot be empty"
        )
    
    if len(text) > MAX_CHARS:
        logger.warning(
            "Text too long in analyze request",
            extra={
                "event": "gcp_llm.analyze.validation_failed",
                "request_id": request_id,
                "text_length": len(text),
                "max_chars": MAX_CHARS,
            }
        )
        raise HTTPException(
            status_code=413,
            detail=f"Text length ({len(text)} chars) exceeds maximum ({MAX_CHARS} chars)"
        )
    
    # Calculate token count (approximate)
    token_count = count_tokens_approx(text)
    
    logger.info(
        "LLM analysis started",
        extra={
            "event": "gcp_llm.analyze.started",
            "request_id": request_id,
            "text_length": len(text),
            "token_count": token_count,
            "doc_type": doc_type,
            "mime_type": mime_type,
            "model_name": MODEL_NAME,
        }
    )
    
    try:
        # Call Gemini
        result = await call_gemini_async(text, doc_type)
        
        # Build entities list
        entities = result.get("entities", [])
        
        # Add TOKEN_COUNT entity (required)
        entities.append({
            "type": "TOKEN_COUNT",
            "value": token_count
        })
        
        # Add DOC_TYPE entity if provided
        if doc_type:
            entities.append({
                "type": "DOC_TYPE",
                "value": doc_type
            })
        
        summary = result.get("summary", "")
        
        duration_ms = (time.time() - start_time) * 1000
        
        logger.info(
            "LLM analysis completed",
            extra={
                "event": "gcp_llm.analyze.success",
                "request_id": request_id,
                "text_length": len(text),
                "token_count": token_count,
                "doc_type": doc_type,
                "mime_type": mime_type,
                "model_name": MODEL_NAME,
                "summary_length": len(summary),
                "entities_count": len(entities),
                "duration_ms": round(duration_ms, 2),
            }
        )
        
        return AnalyzeResponse(
            summary=summary,
            entities=entities
        )
        
    except TimeoutError as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            "LLM analysis timed out",
            extra={
                "event": "gcp_llm.analyze.timeout",
                "request_id": request_id,
                "text_length": len(text),
                "token_count": token_count,
                "doc_type": doc_type,
                "mime_type": mime_type,
                "model_name": MODEL_NAME,
                "duration_ms": round(duration_ms, 2),
                "error": str(e),
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=504,
            detail=f"Request timed out: {str(e)}"
        )
    except gcp_exceptions.GoogleAPIError as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            "Vertex AI API error during LLM analysis",
            extra={
                "event": "gcp_llm.analyze.vertex_error",
                "request_id": request_id,
                "text_length": len(text),
                "token_count": token_count,
                "doc_type": doc_type,
                "mime_type": mime_type,
                "model_name": MODEL_NAME,
                "duration_ms": round(duration_ms, 2),
                "error": str(e),
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=502,
            detail=f"Vertex AI error: {str(e)}"
        )
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            "LLM analysis failed",
            extra={
                "event": "gcp_llm.analyze.failure",
                "request_id": request_id,
                "text_length": len(text),
                "token_count": token_count,
                "doc_type": doc_type,
                "mime_type": mime_type,
                "model_name": MODEL_NAME,
                "duration_ms": round(duration_ms, 2),
                "error": str(e),
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {str(e)}"
        )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "model": MODEL_NAME, "region": GCP_REGION}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
