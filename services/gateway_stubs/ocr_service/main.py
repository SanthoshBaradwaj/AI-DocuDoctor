"""OCR Gateway Service Stub - Local development stub for OCR extraction."""
import os
import boto3
from botocore.client import Config
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="OCR Gateway Service Stub")

# MinIO configuration from environment
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "docs")
MINIO_USE_SSL = os.getenv("MINIO_USE_SSL", "false").lower() == "true"


def get_s3_client():
    """Get S3 client configured for MinIO."""
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        use_ssl=MINIO_USE_SSL,
        verify=False if not MINIO_USE_SSL else True,
    )


class ExtractRequest(BaseModel):
    """Request model for OCR extraction."""
    storage_key: str
    mime_type: Optional[str] = None


class ExtractResponse(BaseModel):
    """Response model for OCR extraction."""
    text: str
    page_count: Optional[int] = None
    language: Optional[str] = None


@app.post("/extract", response_model=ExtractResponse)
async def extract_document(request: ExtractRequest):
    """Extract text from a document stored in MinIO.
    
    For text/plain files, reads actual content from MinIO.
    For other file types, returns deterministic fake text.
    """
    storage_key = request.storage_key
    mime_type = request.mime_type or ""
    
    logger.info(
        "OCR extraction requested",
        extra={
            "storage_key": storage_key,
            "mime_type": mime_type,
        }
    )
    
    # For text files, try to read actual content from MinIO
    if storage_key.endswith('.txt') or 'text' in mime_type.lower():
        try:
            s3 = get_s3_client()
            obj = s3.get_object(Bucket=MINIO_BUCKET, Key=storage_key)
            body_bytes = obj["Body"].read()
            text = body_bytes.decode('utf-8', errors='ignore')
            
            if text.strip():
                logger.info(
                    "OCR extraction completed (text file)",
                    extra={
                        "storage_key": storage_key,
                        "text_length": len(text),
                    }
                )
                return ExtractResponse(
                    text=text,
                    page_count=1,
                    language="en"
                )
        except ClientError as e:
            # Check if it's a NoSuchKey error
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == 'NoSuchKey':
                logger.warning(
                    "Object not found in MinIO",
                    extra={"storage_key": storage_key}
                )
                raise HTTPException(
                    status_code=404,
                    detail=f"Object not found: {storage_key}"
                )
            # Re-raise other ClientErrors as 502
            logger.error(
                "MinIO error during OCR extraction",
                extra={
                    "storage_key": storage_key,
                    "error": str(e),
                    "error_code": error_code,
                },
                exc_info=True
            )
            raise HTTPException(
                status_code=502,
                detail=f"Storage error: {error_code}"
            )
        except Exception as e:
            logger.error(
                "Unexpected error during OCR extraction",
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
    
    # For non-text files, return deterministic fake text
    fake_text = f"[STUB_OCR] Extracted text from document: {storage_key}\n\n"
    fake_text += "This is a stub OCR result for local development.\n"
    fake_text += f"Storage key: {storage_key}\n"
    if mime_type:
        fake_text += f"MIME type: {mime_type}\n"
    fake_text += "\nIn production, this would contain actual OCR-extracted text.\n"
    
    logger.info(
        "OCR extraction completed (fake text)",
        extra={
            "storage_key": storage_key,
            "mime_type": mime_type,
            "text_length": len(fake_text),
        }
    )
    
    return ExtractResponse(
        text=fake_text,
        page_count=1,
        language="en"
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)

