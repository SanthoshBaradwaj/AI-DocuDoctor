# AI infrastructure base module
from typing import Protocol, Optional
from pydantic import BaseModel
import httpx
from app.core.config import get_settings
from app.core.logging import get_logger


class OcrResult(BaseModel):
    """Result from OCR extraction."""
    text: str
    page_count: Optional[int] = None
    language: Optional[str] = None


class LlmResult(BaseModel):
    """Result from LLM document analysis."""
    summary: str
    entities: list[dict] = []  # List of entity dicts, e.g., [{"type": "TOKEN_COUNT", "value": 123}]


# Protocol/interface for LLM services
class LLMService(Protocol):
    """Protocol defining the interface for LLM services."""
    
    def generate(self, prompt: str, context: str = "") -> str:
        """Generate a response from the LLM.
        
        Args:
            prompt: The user's prompt/question
            context: Optional context (e.g., document content)
            
        Returns:
            Generated response text
        """
        ...
    
    def analyze_document(
        self,
        *,
        text: str,
        mime_type: Optional[str] = None,
        doc_type: Optional[str] = None,
    ) -> "LlmResult":
        """Analyze a document and extract summary and entities.
        
        Args:
            text: The document text content (from OCR)
            mime_type: Optional MIME type of the document
            doc_type: Optional document type (e.g., "PASSPORT", "BANK_STATEMENT")
            
        Returns:
            LlmResult with summary and entities
        """
        ...

# Protocol/interface for OCR services
class OcrService(Protocol):
    """Protocol defining the interface for OCR services."""
    
    def extract_document(
        self,
        *,
        storage_key: str,
        mime_type: Optional[str] = None,
    ) -> OcrResult:
        """Extract text and metadata from a document in storage.
        
        Args:
            storage_key: The storage key/path of the document
            mime_type: Optional MIME type of the document
            
        Returns:
            OcrResult with extracted text and metadata
        """
        ...

# Fake implementations for local dev
class FakeLLMService:
    """Fake LLM service for local development."""
    
    def generate(self, prompt: str, context: str = "") -> str:
        """Generate a response for chat/conversation."""
        if context:
            return f"(dev mock) Context: {context[:50]}... Response to: {prompt}"
        return f"(dev mock) {prompt}"
    
    def analyze_document(
        self,
        *,
        text: str,
        mime_type: Optional[str] = None,
        doc_type: Optional[str] = None,
    ) -> LlmResult:
        """Analyze a document and extract summary and entities.
        
        For local development, this generates deterministic fake results
        based on the input text. In production, this would call
        a real LLM service (e.g., Gemini, OpenAI, Anthropic).
        
        Args:
            text: The document text content
            mime_type: Optional MIME type of the document
            doc_type: Optional document type
            
        Returns:
            LlmResult with fake summary and entities
        """
        # Generate deterministic fake summary (truncate text + suffix)
        # Mimics the behavior of summarize() from text_utils
        clean_text = " ".join(text.split())
        summary_limit = 240
        if len(clean_text) > summary_limit:
            summary = clean_text[:summary_limit] + "… [fake summary]"
        else:
            summary = clean_text + " [fake summary]" if clean_text else "[fake summary]"
        
        # Generate fake entities (mimics fake_ner behavior)
        entities = [{"type": "TOKEN_COUNT", "value": len(text.split())}]
        
        # Add doc_type-based tags if available
        if doc_type:
            entities.append({"type": "DOC_TYPE", "value": doc_type})
        
        # Add some generic tags
        entities.append({"type": "FAKE_TAG", "value": "test"})
        
        return LlmResult(
            summary=summary,
            entities=entities
        )


class HttpLlmService:
    """HTTP-based LLM service that calls an external LLM microservice."""
    
    def __init__(self, base_url: str, http_client: Optional[httpx.Client] = None, timeout: Optional[float] = None):
        """Initialize HTTP LLM service.
        
        Args:
            base_url: Base URL of the LLM service (e.g., "http://llm-service:8080")
            http_client: Optional httpx client (creates new one if not provided)
            timeout: Optional timeout in seconds (default: 10.0)
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout or 10.0
        if http_client is not None:
            self.http_client = http_client
            self._client_provided = True
        else:
            self.http_client = httpx.Client(timeout=self.timeout)
            self._client_provided = False
        self.logger = get_logger(__name__)
    
    def generate(self, prompt: str, context: str = "") -> str:
        """Generate a response for chat/conversation.
        
        For now, this is a placeholder. HTTP LLM service may support chat
        in the future, but currently only analyze_document is implemented.
        """
        # For HTTP LLM, chat generation would call a different endpoint
        # This is a placeholder to satisfy the LLMService Protocol
        raise NotImplementedError("Chat generation not yet implemented for HttpLlmService")
    
    def analyze_document(
        self,
        *,
        text: str,
        mime_type: Optional[str] = None,
        doc_type: Optional[str] = None,
    ) -> LlmResult:
        """Analyze a document by calling HTTP LLM service.
        
        Args:
            text: The document text content (from OCR)
            mime_type: Optional MIME type of the document
            doc_type: Optional document type (e.g., "PASSPORT", "BANK_STATEMENT")
            
        Returns:
            LlmResult with summary and entities
            
        Raises:
            httpx.HTTPError: If the HTTP request fails
            ValueError: If the response format is invalid
        """
        # Prepare request payload
        payload = {
            "text": text,
        }
        if mime_type:
            payload["mime_type"] = mime_type
        if doc_type:
            payload["doc_type"] = doc_type
        
        # Call LLM service endpoint
        endpoint = f"{self.base_url}/analyze"
        
        try:
            response = self.http_client.post(
                endpoint,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            # Parse response JSON
            data = response.json()
            
            # Validate and map to LlmResult
            if not isinstance(data, dict):
                raise ValueError(f"Invalid response format: expected dict, got {type(data)}")
            
            if "summary" not in data:
                raise ValueError("Invalid LLM service response format: missing 'summary' field")
            
            # Extract summary (required)
            summary = data.get("summary", "")
            if not isinstance(summary, str):
                raise ValueError(f"Invalid LLM service response format: 'summary' must be a string, got {type(summary)}")
            
            # Extract entities (optional, defaults to empty list)
            entities = data.get("entities", [])
            if not isinstance(entities, list):
                raise ValueError(f"Invalid LLM service response format: 'entities' must be a list, got {type(entities)}")
            
            result = LlmResult(
                summary=summary,
                entities=entities
            )
            
            # Log metadata only (not full text or summary)
            self.logger.info(
                "LLM analysis completed via HTTP service",
                extra={
                    "text_length": len(text),
                    "summary_length": len(result.summary),
                    "entities_count": len(result.entities),
                    "mime_type": mime_type,
                    "doc_type": doc_type,
                }
            )
            
            return result
            
        except httpx.HTTPStatusError as e:
            self.logger.error(
                "LLM service returned error status",
                extra={
                    "status_code": e.response.status_code,
                    "response_text": e.response.text[:200],  # First 200 chars only
                    "text_length": len(text),
                },
                exc_info=True
            )
            raise
        except httpx.RequestError as e:
            self.logger.error(
                "LLM service request failed",
                extra={
                    "error": str(e),
                    "text_length": len(text),
                },
                exc_info=True
            )
            raise
        except (KeyError, ValueError, TypeError) as e:
            self.logger.error(
                "Invalid LLM service response format",
                extra={
                    "error": str(e),
                    "text_length": len(text),
                },
                exc_info=True
            )
            raise ValueError(f"Invalid LLM service response: {str(e)}") from e
    
    def __del__(self):
        """Clean up HTTP client if we created it."""
        if self.http_client and not hasattr(self, '_client_provided'):
            try:
                self.http_client.close()
            except Exception:
                pass

class FakeOcrService:
    """Fake OCR service for local development."""
    
    def extract_document(
        self,
        *,
        storage_key: str,
        mime_type: Optional[str] = None,
    ) -> OcrResult:
        """Extract text from a document using fake OCR.
        
        For local development, this generates deterministic fake text
        based on the storage key. In production, this would call
        a real OCR service (e.g., Google Vision, AWS Textract).
        
        Args:
            storage_key: The storage key/path of the document
            mime_type: Optional MIME type of the document
            
        Returns:
            OcrResult with fake extracted text and metadata
        """
        # Generate deterministic fake text based on storage key
        # This simulates OCR extraction without calling external APIs
        fake_text = f"[FAKE_OCR] Dummy text extracted from document: {storage_key}\n\n"
        fake_text += "This is a placeholder OCR result for local development.\n"
        fake_text += "In production, this would contain the actual extracted text from the document.\n"
        fake_text += f"Storage key: {storage_key}\n"
        if mime_type:
            fake_text += f"MIME type: {mime_type}\n"
        
        # For .txt files, try to read actual content from storage
        if storage_key.endswith('.txt') or (mime_type and 'text' in mime_type.lower()):
            try:
                from app.infrastructure.storage.s3_minio import make_s3, get_bucket_name
                s3 = make_s3()
                bucket = get_bucket_name()
                obj = s3.get_object(Bucket=bucket, Key=storage_key)
                body_bytes = obj["Body"].read()
                actual_text = body_bytes.decode('utf-8', errors='ignore')
                if actual_text.strip():
                    fake_text = actual_text
            except Exception:
                # If we can't read from storage, use the fake text
                pass
        
        return OcrResult(
            text=fake_text,
            page_count=1,
            language="en"
        )


class HttpOcrService:
    """HTTP-based OCR service that calls an external OCR microservice."""
    
    def __init__(self, base_url: str, http_client: Optional[httpx.Client] = None):
        """Initialize HTTP OCR service.
        
        Args:
            base_url: Base URL of the OCR service (e.g., "http://ocr-service:8080")
            http_client: Optional httpx client (creates new one if not provided)
        """
        self.base_url = base_url.rstrip('/')
        if http_client is not None:
            self.http_client = http_client
            self._client_provided = True
        else:
            self.http_client = httpx.Client(timeout=60.0)
            self._client_provided = False
        self.logger = get_logger(__name__)
    
    def extract_document(
        self,
        *,
        storage_key: str,
        mime_type: Optional[str] = None,
    ) -> OcrResult:
        """Extract text from a document by calling HTTP OCR service.
        
        Args:
            storage_key: The storage key/path of the document
            mime_type: Optional MIME type of the document
            
        Returns:
            OcrResult with extracted text and metadata
            
        Raises:
            httpx.HTTPError: If the HTTP request fails
            ValueError: If the response format is invalid
        """
        # Prepare request payload
        payload = {
            "storage_key": storage_key,
        }
        if mime_type:
            payload["mime_type"] = mime_type
        
        # Call OCR service endpoint (assumes POST /extract or similar)
        endpoint = f"{self.base_url}/extract"
        
        try:
            response = self.http_client.post(
                endpoint,
                json=payload,
                timeout=60.0
            )
            response.raise_for_status()
            
            # Parse response JSON
            data = response.json()
            
            # Validate and map to OcrResult
            if not isinstance(data, dict):
                raise ValueError(f"Invalid response format: expected dict, got {type(data)}")
            
            if "text" not in data:
                raise ValueError("Invalid OCR service response format: missing 'text' field")
            
            result = OcrResult(
                text=data.get("text", ""),
                page_count=data.get("page_count"),
                language=data.get("language")
            )
            
            # Log metadata only (not full text)
            self.logger.info(
                "OCR extraction completed via HTTP service",
                extra={
                    "storage_key": storage_key,
                    "page_count": result.page_count,
                    "language": result.language,
                    "text_length": len(result.text),
                }
            )
            
            return result
            
        except httpx.HTTPStatusError as e:
            self.logger.error(
                "OCR service returned error status",
                extra={
                    "storage_key": storage_key,
                    "status_code": e.response.status_code,
                    "response_text": e.response.text[:200],  # First 200 chars only
                },
                exc_info=True
            )
            raise
        except httpx.RequestError as e:
            self.logger.error(
                "OCR service request failed",
                extra={
                    "storage_key": storage_key,
                    "error": str(e),
                },
                exc_info=True
            )
            raise
        except (KeyError, ValueError, TypeError) as e:
            self.logger.error(
                "Invalid OCR service response format",
                extra={
                    "storage_key": storage_key,
                    "error": str(e),
                },
                exc_info=True
            )
            raise ValueError(f"Invalid OCR service response: {str(e)}") from e
    
    def __del__(self):
        """Clean up HTTP client if we created it."""
        if self.http_client and not hasattr(self, '_client_provided'):
            try:
                self.http_client.close()
            except Exception:
                pass

# Factory functions
def get_llm_service() -> LLMService:
    """Get the appropriate LLM service based on configuration.
    
    Returns:
        LLMService implementation
        
    Raises:
        RuntimeError: If LLM_PROVIDER is set to an unsupported value
        RuntimeError: If LLM_PROVIDER is "http" but LLM_SERVICE_URL is not set
    """
    settings = get_settings()
    
    if settings.LLM_PROVIDER == "fake":
        return FakeLLMService()
    elif settings.LLM_PROVIDER == "http":
        if not settings.LLM_SERVICE_URL:
            raise RuntimeError(
                "LLM_PROVIDER is set to 'http' but LLM_SERVICE_URL is not configured. "
                "Please set LLM_SERVICE_URL environment variable."
            )
        return HttpLlmService(base_url=settings.LLM_SERVICE_URL)
    else:
        raise RuntimeError(
            f"Unsupported LLM_PROVIDER: {settings.LLM_PROVIDER}. "
            "Supported values: 'fake', 'http'"
        )

def get_ocr_service() -> OcrService:
    """Get the appropriate OCR service based on configuration.
    
    Returns:
        OcrService implementation
        
    Raises:
        ValueError: If OCR_PROVIDER is set to an unsupported value
        ValueError: If OCR_PROVIDER is "http" but OCR_SERVICE_URL is not set
    """
    settings = get_settings()
    
    if settings.OCR_PROVIDER == "fake":
        return FakeOcrService()
    elif settings.OCR_PROVIDER == "http":
        if not settings.OCR_SERVICE_URL:
            raise ValueError(
                "OCR_PROVIDER is set to 'http' but OCR_SERVICE_URL is not configured. "
                "Please set OCR_SERVICE_URL environment variable."
            )
        return HttpOcrService(base_url=settings.OCR_SERVICE_URL)
    else:
        raise ValueError(
            f"Unsupported OCR_PROVIDER: {settings.OCR_PROVIDER}. "
            "Supported values: 'fake', 'http'"
        )
