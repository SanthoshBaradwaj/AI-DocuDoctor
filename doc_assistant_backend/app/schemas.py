from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict, Any
from datetime import date

# Document schemas
class DocOut(BaseModel):
    id: int
    title: str
    filename: str
    status: str
    ocr_status: str  # OCR lifecycle status: pending, processing, ready, error
    llm_status: str  # LLM lifecycle status: pending, processing, ready, error
    excerpt: str
    extracted: Optional[dict] = None
    domain: Optional[str] = None  # DocumentDomain enum value as string
    doc_type: Optional[str] = None  # DocumentType enum value as string
    expiry_date: Optional[date] = None
    class Config: from_attributes = True

class DocDetailOut(DocOut):
    body: str

# Upload schemas
class UploadInitIn(BaseModel):
    """Request schema for initializing an upload."""
    filename: str
    mime_type: str
    size_bytes: int
    domain: Optional[str] = None  # Optional hint for document domain
    doc_type: Optional[str] = None  # Optional hint for document type

class UploadInitOut(BaseModel):
    """Response schema for upload initialization."""
    storage_key: str  # Internal key/path
    upload_url: str  # Presigned URL for upload
    upload_fields: Optional[Dict[str, Any]] = None  # POST-style presigned fields
    max_size_bytes: int

class UploadNotifyIn(BaseModel):
    """Request schema for notifying upload completion."""
    storage_key: str
    filename: str
    mime_type: str
    size_bytes: int
    domain: Optional[str] = None
    doc_type: Optional[str] = None

# Legacy schemas (kept for backward compatibility during transition)
class PresignOut(BaseModel):
    url: str
    fields: dict = {}
    key: str

class NotifyIn(BaseModel):
    key: str
    filename: str
    size: int
    mime: Optional[str] = "application/octet-stream"

# Analysis schemas (transitional - will be superseded by async pipeline)
class AnalyzeIn(BaseModel):
    docId: int

class BatchAnalyzeIn(BaseModel):
    docIds: List[int] = Field(default_factory=list)

# Chat schemas
class ChatMessageIn(BaseModel):
    """Individual chat message."""
    role: Literal["user", "assistant", "system"]
    content: str

class ChatRequestIn(BaseModel):
    """Request schema for chat endpoints."""
    messages: List[ChatMessageIn]

class ChatResponseOut(BaseModel):
    """Response schema for chat endpoints."""
    reply: str
    messages: List[ChatMessageIn]  # Full conversation including assistant response

# Legacy chat schemas (kept for backward compatibility)
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatIn(BaseModel):
    docId: Optional[int] = None
    messages: List[ChatMessage]

class ChatOut(BaseModel):
    reply: str
