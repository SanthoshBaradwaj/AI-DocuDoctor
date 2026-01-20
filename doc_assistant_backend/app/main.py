from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import uuid
import traceback
from typing import Optional

from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.api.v1 import docs, chat, health

# Setup logging first
setup_logging()
logger = get_logger(__name__)

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    docs_url="/api-docs",
    redoc_url=None,
    openapi_url="/openapi.json",
)

# CORS configuration
allow_origins = ["*"] if settings.APP_ENV == "local" else ["https://yourdomain.com"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware to generate and attach request IDs to requests and responses."""
    
    async def dispatch(self, request: Request, call_next):
        # Get or generate request ID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # Attach to request state
        request.state.request_id = request_id
        
        # Set in logging context
        from app.core.logging import _request_id
        _request_id.set(request_id)
        
        # Process request
        response = await call_next(request)
        
        # Add request ID to response header
        response.headers["X-Request-ID"] = request_id
        
        return response


app.add_middleware(RequestIdMiddleware)


# Global exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent error response format.
    
    If exc.detail is already a normalized error dict, use it directly.
    Otherwise, normalize it to the standard format.
    """
    request_id = getattr(request.state, "request_id", None)
    
    # Check if detail is already a normalized error dict
    if isinstance(exc.detail, dict) and "error_code" in exc.detail:
        # Already normalized - use it directly
        error_response = exc.detail.copy()
        # Ensure request_id is set
        if not error_response.get("request_id"):
            error_response["request_id"] = request_id
        logger.warning(
            "HTTP exception",
            extra={
                "request_id": request_id,
                "error_code": error_response.get("error_code"),
                "status_code": exc.status_code,
                "path": request.url.path,
                "method": request.method,
            }
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response
        )
    
    # Not normalized - normalize it
    error_code_map = {
        400: "VALIDATION_ERROR",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        413: "PAYLOAD_TOO_LARGE",
        422: "VALIDATION_ERROR",
        500: "INTERNAL_ERROR",
        502: "BAD_GATEWAY",
        504: "GATEWAY_TIMEOUT",
    }
    
    error_code = error_code_map.get(exc.status_code, "HTTP_ERROR")
    
    # Convert detail to string message
    if isinstance(exc.detail, dict):
        # If detail is a dict, try to extract a message
        message = exc.detail.get("message", str(exc.detail))
        details = exc.detail.get("details")
    else:
        message = str(exc.detail) if exc.detail else "An error occurred"
        details = None
    
    logger.warning(
        "HTTP exception",
        extra={
            "request_id": request_id,
            "error_code": error_code,
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method,
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": error_code,
            "message": message,
            "details": details,
            "request_id": request_id,
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions with consistent error response format.
    
    This handler catches any unhandled exceptions and ensures they are:
    - Logged with full stacktrace (exc_info=True)
    - Returned as JSON with error_code and request_id
    - Never expose internal error details to clients
    """
    request_id = getattr(request.state, "request_id", None)
    
    # Log with full stacktrace to stdout/stderr (Cloud Run will capture this)
    logger.error(
        "Unhandled exception",
        extra={
            "request_id": request_id,
            "error_code": "INTERNAL_ERROR",
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "path": request.url.path,
            "method": request.method,
        },
        exc_info=True  # This ensures full stacktrace is logged
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_ERROR",
            "message": "An internal error occurred. Please try again later.",
            "request_id": request_id,
        }
    )


# Store settings in app state for global access
@app.on_event("startup")
async def startup_event():
    app.state.settings = settings
    logger.info("Application startup", extra={"app_name": settings.APP_NAME, "app_env": settings.APP_ENV})


# Include versioned routers
app.include_router(health.router)
app.include_router(docs.router)
app.include_router(chat.router)
