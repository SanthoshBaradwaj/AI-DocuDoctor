"""Centralized constants and enums for the application."""
from enum import Enum


class PipelineStepStatus(str, Enum):
    """Status values for pipeline processing steps (OCR, LLM)."""
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"

