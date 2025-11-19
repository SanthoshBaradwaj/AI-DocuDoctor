# AI infrastructure base module
from typing import Protocol
from app.core.config import get_settings

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

# Protocol/interface for OCR services
class OcrService(Protocol):
    """Protocol defining the interface for OCR services."""
    
    def extract_text(self, file_bytes: bytes, filename: str) -> str:
        """Extract text from a file.
        
        Args:
            file_bytes: The file content as bytes
            filename: The filename (for format detection)
            
        Returns:
            Extracted text
        """
        ...

# Fake implementations for local dev
class FakeLLMService:
    """Fake LLM service for local development."""
    
    def generate(self, prompt: str, context: str = "") -> str:
        if context:
            return f"(dev mock) Context: {context[:50]}... Response to: {prompt}"
        return f"(dev mock) {prompt}"

class FakeOcrService:
    """Fake OCR service for local development."""
    
    def extract_text(self, file_bytes: bytes, filename: str) -> str:
        # Simple text extraction for .txt files
        if filename.lower().endswith('.txt'):
            try:
                return file_bytes.decode('utf-8', errors='ignore')
            except Exception:
                return f"[extract error] Could not decode {filename}"
        return f"Uploaded file: {filename} (binary preview not implemented in dev)"

# Factory functions
def get_llm_service() -> LLMService:
    """Get the appropriate LLM service based on configuration."""
    settings = get_settings()
    
    if settings.AI_BACKEND == "fake":
        return FakeLLMService()
    # Gemini/OpenAI/Bedrock will be added later
    return FakeLLMService()

def get_ocr_service() -> OcrService:
    """Get the appropriate OCR service based on configuration."""
    settings = get_settings()
    
    if settings.AI_BACKEND == "fake":
        return FakeOcrService()
    # Gemini Vision/other OCR services will be added later
    return FakeOcrService()
