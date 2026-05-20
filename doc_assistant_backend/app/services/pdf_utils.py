"""PDF utilities for page counting and validation."""
from io import BytesIO
from typing import Optional
from pypdf import PdfReader
from app.core.logging import get_logger

logger = get_logger(__name__)


def count_pdf_pages(pdf_bytes: bytes) -> int:
    """Count pages in a PDF file.
    
    Args:
        pdf_bytes: PDF file content as bytes
        
    Returns:
        Number of pages in the PDF
        
    Raises:
        ValueError: If file is not a valid PDF
    """
    try:
        pdf_file = BytesIO(pdf_bytes)
        reader = PdfReader(pdf_file)
        page_count = len(reader.pages)
        logger.debug(
            "PDF page count extracted",
            extra={
                "page_count": page_count,
                "pdf_size_bytes": len(pdf_bytes),
            }
        )
        return page_count
    except Exception as e:
        logger.error(
            "Failed to count PDF pages",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "pdf_size_bytes": len(pdf_bytes),
            },
            exc_info=True
        )
        raise ValueError(f"Invalid PDF file: {str(e)}") from e
