"""GCP Vision OCR Gateway Service - Cloud Run deployable OCR service using Google Cloud Vision API."""
import os
import json
import time
import uuid
import logging
from typing import Optional
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from google.cloud import vision
from google.cloud import storage
from google.api_core import exceptions as gcp_exceptions
import json

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="GCP Vision OCR Gateway Service")

# Configuration from environment
GCS_BUCKET = os.getenv("GCS_BUCKET", "")
GCS_OUTPUT_BUCKET = os.getenv("GCS_OUTPUT_BUCKET", GCS_BUCKET)
GCS_OUTPUT_PREFIX = os.getenv("GCS_OUTPUT_PREFIX", "ocr-output/")
OCR_TIMEOUT_SECONDS = int(os.getenv("OCR_TIMEOUT_SECONDS", "120"))
MAX_BYTES = int(os.getenv("MAX_BYTES", str(10 * 1024 * 1024)))  # 10MB default

# Initialize GCP clients
vision_client = vision.ImageAnnotatorClient()
storage_client = storage.Client()


class ExtractRequest(BaseModel):
    """Request model for OCR extraction."""
    storage_key: str
    mime_type: Optional[str] = "application/octet-stream"


class ExtractResponse(BaseModel):
    """Response model for OCR extraction."""
    text: str
    page_count: Optional[int] = None
    language: Optional[str] = None


def parse_storage_key(storage_key: str) -> tuple[str, str]:
    """Parse storage_key into (bucket, object_path).
    
    Supports:
    - gs://bucket/path/to/object -> (bucket, path/to/object)
    - path/to/object -> (GCS_BUCKET env, path/to/object)
    
    Returns:
        Tuple of (bucket, object_path)
    """
    if storage_key.startswith("gs://"):
        # Parse gs:// URL
        parsed = urlparse(storage_key)
        bucket = parsed.netloc
        object_path = parsed.path.lstrip('/')
        return bucket, object_path
    else:
        # Use object path as-is, bucket from env
        if not GCS_BUCKET:
            raise ValueError("GCS_BUCKET environment variable is required when storage_key is not a gs:// URL")
        return GCS_BUCKET, storage_key


def extract_text_from_image_bytes(image_bytes: bytes) -> tuple[str, Optional[int], Optional[str]]:
    """Extract text from image bytes using Vision API.
    
    Args:
        image_bytes: Image file bytes
        
    Returns:
        Tuple of (text, page_count, language)
    """
    image = vision.Image(content=image_bytes)
    response = vision_client.text_detection(image=image)
    
    if response.error.message:
        raise RuntimeError(f"Vision API error: {response.error.message}")
    
    # Extract full text
    full_text = ""
    if response.full_text_annotation:
        full_text = response.full_text_annotation.text
        # Get detected language
        detected_language = None
        if response.full_text_annotation.pages:
            # Get language from first page
            page = response.full_text_annotation.pages[0]
            if page.property and page.property.detected_languages:
                detected_language = page.property.detected_languages[0].language_code
        return full_text, 1, detected_language or "en"
    
    return "", 1, "en"


def extract_text_from_gcs_async(bucket: str, object_path: str, output_bucket: str, output_prefix: str) -> tuple[str, Optional[int], Optional[str]]:
    """Extract text from PDF/TIFF using Vision async batch processing.
    
    Args:
        bucket: GCS bucket name
        object_path: GCS object path
        output_bucket: GCS bucket for output
        output_prefix: GCS prefix for output
        
    Returns:
        Tuple of (text, page_count, language)
        
    Raises:
        HTTPException: For all errors (504 for timeout, 502 for API errors)
    """
    # Create unique output path
    job_id = str(uuid.uuid4())
    output_path = f"{output_prefix}{job_id}/"
    
    # Configure async request
    gcs_source_uri = f"gs://{bucket}/{object_path}"
    gcs_destination_uri = f"gs://{output_bucket}/{output_path}"
    
    logger.info(
        "Starting async OCR batch processing",
        extra={
            "event": "gcp_ocr.extract.async_started",
            "gcs_source": gcs_source_uri,
            "gcs_destination": gcs_destination_uri,
        }
    )
    
    # Start async batch operation
    source = vision.GcsSource(uri=gcs_source_uri)
    destination = vision.GcsDestination(uri=gcs_destination_uri)
    
    # Determine MIME type from object path
    mime_type = "application/pdf"
    if object_path.lower().endswith('.tiff') or object_path.lower().endswith('.tif'):
        mime_type = "image/tiff"
    
    async_request = vision.AsyncAnnotateFileRequest(
        input_config=vision.InputConfig(
            gcs_source=source,
            mime_type=mime_type
        ),
        features=[vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)],
        output_config=vision.OutputConfig(
            gcs_destination=destination,
            batch_size=100
        )
    )
    
    try:
        operation = vision_client.async_batch_annotate_files(requests=[async_request])
        
        # Wait for operation completion using result() with timeout
        # This replaces the polling loop with operation.reload()
        try:
            operation.result(timeout=OCR_TIMEOUT_SECONDS)
        except gcp_exceptions.DeadlineExceeded:
            logger.error(
                "OCR operation timed out",
                extra={
                    "event": "gcp_ocr.extract.timeout",
                    "storage_key": f"gs://{bucket}/{object_path}",
                    "timeout_seconds": OCR_TIMEOUT_SECONDS,
                }
            )
            raise HTTPException(
                status_code=504,
                detail=f"OCR operation timed out after {OCR_TIMEOUT_SECONDS} seconds"
            )
        
        # Check for operation errors
        if hasattr(operation, 'error') and operation.error:
            error_msg = f"Vision API operation error: {operation.error}"
            logger.error(
                "OCR operation failed",
                extra={
                    "event": "gcp_ocr.extract.operation_error",
                    "storage_key": f"gs://{bucket}/{object_path}",
                    "error": error_msg,
                }
            )
            raise HTTPException(
                status_code=502,
                detail=error_msg
            )
    except HTTPException:
        # Re-raise HTTPExceptions (timeout, operation errors)
        raise
    except Exception as e:
        # Catch any other exceptions (AttributeError, etc.) and convert to HTTPException
        error_msg = f"Vision API error: {str(e)}"
        logger.error(
            "OCR operation failed",
            extra={
                "event": "gcp_ocr.extract.failure",
                "storage_key": f"gs://{bucket}/{object_path}",
                "error": error_msg,
                "error_type": type(e).__name__,
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=502,
            detail=error_msg
        )
    
    # Read output files from GCS
    try:
        output_bucket_obj = storage_client.bucket(output_bucket)
        blobs = list(output_bucket_obj.list_blobs(prefix=output_path))
        
        if not blobs:
            error_msg = "No output files found from Vision API"
            logger.error(
                "OCR operation failed - no output files",
                extra={
                    "event": "gcp_ocr.extract.no_output",
                    "storage_key": f"gs://{bucket}/{object_path}",
                    "output_path": output_path,
                }
            )
            raise HTTPException(
                status_code=502,
                detail=error_msg
            )
    except HTTPException:
        raise
    except Exception as e:
        # Catch any AttributeError or other exceptions when accessing GCS
        error_msg = f"Error reading OCR output from GCS: {str(e)}"
        logger.error(
            "OCR operation failed - GCS read error",
            extra={
                "event": "gcp_ocr.extract.gcs_error",
                "storage_key": f"gs://{bucket}/{object_path}",
                "error": error_msg,
                "error_type": type(e).__name__,
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=502,
            detail=error_msg
        )
    
    # Sort blobs by name (to maintain page order)
    blobs.sort(key=lambda b: b.name)
    
    # Concatenate text from all output files
    full_text_parts = []
    page_count = 0
    detected_languages = []
    
    try:
        for blob in blobs:
            if blob.name.endswith('.json'):
                # Read JSON response
                json_content = blob.download_as_text()
                response_data = json.loads(json_content)
                
                # Extract text from responses
                if 'responses' in response_data:
                    for response in response_data['responses']:
                        if 'fullTextAnnotation' in response:
                            annotation = response['fullTextAnnotation']
                            if 'text' in annotation:
                                full_text_parts.append(annotation['text'])
                                # Count pages from annotation
                                if 'pages' in annotation:
                                    page_count += len(annotation['pages'])
                                else:
                                    page_count += 1
                            
                            # Extract language if available
                            if 'pages' in annotation:
                                for page in annotation['pages']:
                                    if 'property' in page and 'detectedLanguages' in page['property']:
                                        for lang in page['property']['detectedLanguages']:
                                            if lang.get('languageCode'):
                                                detected_languages.append(lang['languageCode'])
    except Exception as e:
        # Catch any AttributeError or other exceptions when parsing JSON
        error_msg = f"Error parsing OCR output JSON: {str(e)}"
        logger.error(
            "OCR operation failed - JSON parse error",
            extra={
                "event": "gcp_ocr.extract.parse_error",
                "storage_key": f"gs://{bucket}/{object_path}",
                "error": error_msg,
                "error_type": type(e).__name__,
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=502,
            detail=error_msg
        )
    
    full_text = "\n\n".join(full_text_parts)
    # If no pages counted, estimate from number of output files
    if page_count == 0:
        page_count = len([b for b in blobs if b.name.endswith('.json')])
    language = detected_languages[0] if detected_languages else "en"
    
    logger.info(
        "Async OCR batch processing completed",
        extra={
            "event": "gcp_ocr.extract.async_completed",
            "page_count": page_count,
            "text_length": len(full_text),
            "language": language,
        }
    )
    
    return full_text, page_count, language


@app.post("/extract", response_model=ExtractResponse)
async def extract_document(
    request: ExtractRequest,
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID")
):
    """Extract text from a document stored in GCS using Google Cloud Vision API.
    
    Supports:
    - PDF/TIFF: Uses async batch processing with GCS input/output
    - Images: Uses direct Vision API calls
    - Text files: Reads directly from GCS
    """
    start_time = time.time()
    storage_key = request.storage_key
    mime_type = request.mime_type or "application/octet-stream"
    
    # Validate request
    if not storage_key or not storage_key.strip():
        raise HTTPException(
            status_code=400,
            detail="storage_key is required and cannot be empty"
        )
    
    logger.info(
        "OCR extraction requested",
        extra={
            "event": "gcp_ocr.extract.started",
            "storage_key": storage_key,
            "mime_type": mime_type,
            "request_id": x_request_id,
        }
    )
    
    try:
        # Parse storage key
        bucket, object_path = parse_storage_key(storage_key)
        
        # Handle text files directly
        if mime_type == "text/plain":
            try:
                bucket_obj = storage_client.bucket(bucket)
                blob = bucket_obj.blob(object_path)
                text = blob.download_as_text()
                
                duration_ms = (time.time() - start_time) * 1000
                logger.info(
                    "OCR extraction completed (text file)",
                    extra={
                        "event": "gcp_ocr.extract.success",
                        "storage_key": storage_key,
                        "text_length": len(text),
                        "page_count": 1,
                        "duration_ms": round(duration_ms, 2),
                        "request_id": x_request_id,
                    }
                )
                
                return ExtractResponse(
                    text=text,
                    page_count=1,
                    language="en"
                )
            except gcp_exceptions.NotFound:
                raise HTTPException(
                    status_code=404,
                    detail=f"Object not found: {storage_key}"
                )
            except Exception as e:
                logger.error(
                    "GCS error during text file read",
                    extra={
                        "storage_key": storage_key,
                        "error": str(e),
                    },
                    exc_info=True
                )
                raise HTTPException(
                    status_code=502,
                    detail=f"Storage error: {str(e)}"
                )
        
        # Handle PDF/TIFF with async batch processing
        if mime_type in ["application/pdf", "image/tiff"]:
            try:
                text, page_count, language = extract_text_from_gcs_async(
                    bucket, object_path, GCS_OUTPUT_BUCKET, GCS_OUTPUT_PREFIX
                )
                
                duration_ms = (time.time() - start_time) * 1000
                logger.info(
                    "OCR extraction completed (async batch)",
                    extra={
                        "event": "gcp_ocr.extract.success",
                        "storage_key": storage_key,
                        "text_length": len(text),
                        "page_count": page_count,
                        "language": language,
                        "duration_ms": round(duration_ms, 2),
                        "request_id": x_request_id,
                    }
                )
                
                return ExtractResponse(
                    text=text,
                    page_count=page_count,
                    language=language
                )
            except HTTPException:
                # Re-raise HTTPExceptions (already properly formatted)
                raise
            except Exception as e:
                # Catch any unexpected exceptions and convert to HTTPException
                error_msg = f"Vision API error: {str(e)}"
                logger.error(
                    "OCR operation failed",
                    extra={
                        "event": "gcp_ocr.extract.failure",
                        "storage_key": storage_key,
                        "error": error_msg,
                        "error_type": type(e).__name__,
                    },
                    exc_info=True
                )
                raise HTTPException(
                    status_code=502,
                    detail=error_msg
                )
        
        # Handle images with direct Vision API
        try:
            # Download file from GCS (with size limit)
            bucket_obj = storage_client.bucket(bucket)
            blob = bucket_obj.blob(object_path)
            
            # Check size
            blob.reload()
            if blob.size > MAX_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"File size ({blob.size} bytes) exceeds maximum ({MAX_BYTES} bytes)"
                )
            
            image_bytes = blob.download_as_bytes()
            text, page_count, language = extract_text_from_image_bytes(image_bytes)
            
            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                "OCR extraction completed (image)",
                extra={
                    "event": "gcp_ocr.extract.success",
                    "storage_key": storage_key,
                    "text_length": len(text),
                    "page_count": page_count,
                    "language": language,
                    "duration_ms": round(duration_ms, 2),
                    "request_id": x_request_id,
                }
            )
            
            return ExtractResponse(
                text=text,
                page_count=page_count,
                language=language
            )
        except gcp_exceptions.NotFound:
            raise HTTPException(
                status_code=404,
                detail=f"Object not found: {storage_key}"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "Error during image OCR",
                extra={
                    "storage_key": storage_key,
                    "error": str(e),
                },
                exc_info=True
            )
            raise HTTPException(
                status_code=502,
                detail=f"OCR error: {str(e)}"
            )
    
    except ValueError as e:
        # Parsing error
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            "OCR extraction failed",
            extra={
                "event": "gcp_ocr.extract.failure",
                "storage_key": storage_key,
                "error": str(e),
                "duration_ms": round(duration_ms, 2),
                "request_id": x_request_id,
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
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8081"))
    uvicorn.run(app, host="0.0.0.0", port=port)

