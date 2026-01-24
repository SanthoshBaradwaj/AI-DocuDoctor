"""Shared error handling utilities for consistent error responses across all endpoints."""
from typing import Optional, Dict, Any
import json
import httpx


def normalize_error_response(
    error_code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Normalize error response to consistent format.
    
    All API errors should use this format:
    {
        "error_code": "string",
        "message": "string",  # Always human-readable
        "details": object | null,
        "request_id": "string"
    }
    
    Args:
        error_code: Error code string (e.g., "VALIDATION_ERROR", "LLM_TIMEOUT")
        message: Human-readable error message (always a string, never an object)
        details: Optional details object (for upstream errors, validation details, etc.)
        request_id: Optional request ID for correlation
        
    Returns:
        Normalized error dict ready for HTTPException detail
        
    Example:
        >>> normalize_error_response(
        ...     "LLM_TIMEOUT",
        ...     "LLM service timed out",
        ...     details={"doc_id": "123"},
        ...     request_id="req-456"
        ... )
        {
            "error_code": "LLM_TIMEOUT",
            "message": "LLM service timed out",
            "details": {"doc_id": "123"},
            "request_id": "req-456"
        }
    """
    return {
        "error_code": error_code,
        "message": str(message),  # Ensure message is always a string
        "details": details,
        "request_id": request_id,
    }


def extract_upstream_error_details(response: httpx.Response) -> Optional[Dict[str, Any]]:
    """Extract error details from upstream service response.
    
    If the upstream service returns a JSON error body, extract it into details
    (not into message) to prevent nested error structures.
    
    Args:
        response: HTTP response from upstream service
        
    Returns:
        Dict with error details or None if not extractable
        
    Example:
        If upstream returns:
        {
            "error_code": "MODEL_NOT_FOUND",
            "message": "Model not available",
            "details": {"model": "gemini-2.0"}
        }
        
        Returns:
        {
            "upstream_error_code": "MODEL_NOT_FOUND",
            "upstream_message": "Model not available",
            "upstream_details": {"model": "gemini-2.0"}
        }
    """
    try:
        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("application/json"):
            return None
            
        error_body = response.json()
        if not isinstance(error_body, dict):
            return None
        
        # Extract relevant fields from upstream error
        details = {}
        if "error_code" in error_body:
            details["upstream_error_code"] = error_body["error_code"]
        if "message" in error_body:
            details["upstream_message"] = error_body["message"]
        if "details" in error_body:
            details["upstream_details"] = error_body["details"]
        
        # Include full error body if it's not too large (for debugging)
        error_body_str = json.dumps(error_body)
        if len(error_body_str) < 1000:
            details["upstream_response"] = error_body
        
        return details if details else None
        
    except (json.JSONDecodeError, ValueError, TypeError, AttributeError):
        # If we can't parse JSON or response is invalid, return None
        return None


def map_status_to_error_code(status_code: int) -> str:
    """Map HTTP status code to standard error code.
    
    Args:
        status_code: HTTP status code
        
    Returns:
        Standard error code string
    """
    error_code_map = {
        400: "VALIDATION_ERROR",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        413: "PAYLOAD_TOO_LARGE",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMIT_EXCEEDED",
        500: "INTERNAL_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
        504: "GATEWAY_TIMEOUT",
    }
    return error_code_map.get(status_code, "HTTP_ERROR")
