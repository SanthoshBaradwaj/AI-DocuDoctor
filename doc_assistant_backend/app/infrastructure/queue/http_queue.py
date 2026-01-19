"""HTTP-based task queue implementation for Cloud Run."""
import httpx
from typing import Optional
from app.core.config import get_settings
from app.core.logging import get_logger
from app.infrastructure.queue.base import TaskQueue

settings = get_settings()
logger = get_logger(__name__)


class HttpTaskQueue:
    """HTTP-based implementation of TaskQueue that calls the backend's /process endpoint."""
    
    def __init__(self):
        self.base_url = settings.PUBLIC_BASE_URL
        if not self.base_url:
            raise ValueError("PUBLIC_BASE_URL environment variable is required for HTTP task queue")
        # Remove trailing slash
        self.base_url = self.base_url.rstrip("/")
        self.timeout = 5.0  # Short timeout for fire-and-forget
    
    def enqueue_ocr(self, document_id: int) -> None:
        """Enqueue an OCR task by calling the backend's /process endpoint asynchronously.
        
        This is a best-effort async call - errors are logged but not raised.
        
        Args:
            document_id: The ID of the document to process
        """
        logger.info(
            "Enqueuing OCR task via HTTP",
            extra={
                "document_id": document_id,
                "queue_backend": "http",
                "base_url": self.base_url,
            }
        )
        
        # Construct process endpoint URL
        process_url = f"{self.base_url}/api/v1/docs/{document_id}/process"
        
        # Make async HTTP call (fire-and-forget)
        try:
            # Use httpx.AsyncClient for true async, but for simplicity use sync with timeout
            with httpx.Client(timeout=self.timeout) as client:
                # Best-effort POST - don't wait for response
                try:
                    response = client.post(
                        process_url,
                        json={"step": "ocr"},  # Optional: specify which step to process
                        timeout=self.timeout,
                    )
                    response.raise_for_status()
                    logger.info(
                        "OCR task queued successfully via HTTP",
                        extra={
                            "document_id": document_id,
                            "status_code": response.status_code,
                        }
                    )
                except httpx.TimeoutException:
                    # Timeout is expected for fire-and-forget
                    logger.debug(
                        "HTTP task queue request timed out (expected for async)",
                        extra={"document_id": document_id}
                    )
                except httpx.HTTPStatusError as e:
                    logger.warning(
                        "HTTP task queue request failed",
                        extra={
                            "document_id": document_id,
                            "status_code": e.response.status_code,
                            "error": str(e),
                        }
                    )
                except Exception as e:
                    logger.error(
                        "Unexpected error enqueuing task via HTTP",
                        extra={
                            "document_id": document_id,
                            "error": str(e),
                        },
                        exc_info=True
                    )
        except Exception as e:
            logger.error(
                "Failed to enqueue OCR task via HTTP",
                extra={
                    "document_id": document_id,
                    "error": str(e),
                },
                exc_info=True
            )
