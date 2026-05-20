from datetime import date, datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, Text, JSON, Date, DateTime
from sqlalchemy.sql import func
from app.core.constants import PipelineStepStatus
from .sql_alchemy import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(32), default="user")

class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(512))
    filename: Mapped[str] = mapped_column(String(512))
    s3_key: Mapped[str] = mapped_column(String(1024))
    size: Mapped[int] = mapped_column(Integer, default=0)
    mime: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    status: Mapped[str] = mapped_column(String(32), default="uploaded")
    ocr_status: Mapped[str] = mapped_column(String(32), default=PipelineStepStatus.PENDING.value)
    llm_status: Mapped[str] = mapped_column(String(32), default=PipelineStepStatus.PENDING.value)
    excerpt: Mapped[str] = mapped_column(String(1024), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    extracted: Mapped[dict | None] = mapped_column(JSON, default=None)
    
    # Domain and document type fields
    domain: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    doc_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    # Traceability
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)  # Request ID from API call
    
    # Cost guardrails (EPIC 3)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)  # PDF page count
    ocr_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)  # OCR text character count
    llm_chars_sent: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Characters sent to LLM
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

