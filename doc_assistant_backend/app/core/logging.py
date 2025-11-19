"""Logging configuration with structured JSON-like formatting and request ID support."""
import logging
import sys
import json
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Dict, Optional
from app.core.config import get_settings

settings = get_settings()

# Context variable for request ID
_request_id: ContextVar[Optional[str]] = ContextVar('request_id', default=None)


class StructuredFormatter(logging.Formatter):
    """JSON-like structured formatter for logs."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add request_id if available (from context or record)
        request_id = None
        if hasattr(record, 'request_id') and record.request_id:
            request_id = record.request_id
        else:
            try:
                request_id = _request_id.get()
            except LookupError:
                pass
        
        if request_id:
            log_data["request_id"] = request_id
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename', 'funcName',
                          'levelname', 'levelno', 'lineno', 'module', 'msecs',
                          'message', 'pathname', 'process', 'processName', 'relativeCreated',
                          'thread', 'threadName', 'exc_info', 'exc_text', 'stack_info',
                          'request_id']:
                log_data[key] = value
        
        return json.dumps(log_data, default=str)


def setup_logging():
    """Configure root logger with structured formatting."""
    log_level = getattr(settings, 'LOG_LEVEL', 'INFO').upper()
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Create console handler with structured formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level, logging.INFO))
    console_handler.setFormatter(StructuredFormatter())
    
    root_logger.addHandler(console_handler)
    
    # Configure uvicorn loggers to use our formatter
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.handlers.clear()
    uvicorn_logger.addHandler(console_handler)
    uvicorn_logger.propagate = False
    
    uvicorn_error_logger = logging.getLogger("uvicorn.error")
    uvicorn_error_logger.handlers.clear()
    uvicorn_error_logger.addHandler(console_handler)
    uvicorn_error_logger.propagate = False
    
    # Configure access logger
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.handlers.clear()
    uvicorn_access_logger.addHandler(console_handler)
    uvicorn_access_logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Get a module-level logger with structured formatting.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    # Ensure logging is set up
    if not logging.getLogger().handlers:
        setup_logging()
    
    logger = logging.getLogger(name)
    return logger


# Initialize logging on module import
setup_logging()
