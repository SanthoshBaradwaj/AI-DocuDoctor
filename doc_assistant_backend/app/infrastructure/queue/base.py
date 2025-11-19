"""TaskQueue protocol/interface for background job queuing."""
from typing import Protocol


class TaskQueue(Protocol):
    """Protocol defining the interface for task queue backends."""
    
    def enqueue_ocr(self, document_id: int) -> None:
        """Enqueue an OCR task for a document.
        
        Args:
            document_id: The ID of the document to process
        """
        ...

