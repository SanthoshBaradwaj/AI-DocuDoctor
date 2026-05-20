from pydantic_settings import BaseSettings
from pydantic import AnyUrl
from functools import lru_cache
from typing import Literal, Optional

class Settings(BaseSettings):
    # Environment / deployment
    APP_ENV: Literal["local", "gcp", "aws"] = "local"
    APP_NAME: str = "doc_assistant"

    # API
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: Optional[AnyUrl] = None
    DB_PROVIDER: Literal["sql", "firestore"] = "sql"  # Database provider selection

    # Storage backend selection
    STORAGE_BACKEND: Literal["s3_minio", "gcs", "s3_aws"] = "s3_minio"
    STORAGE_PROVIDER: Optional[Literal["minio", "gcs", "s3_aws"]] = None  # Alias for STORAGE_BACKEND

    # Storage (S3/MinIO) settings for local
    S3_ENDPOINT: Optional[str] = None
    S3_BUCKET: Optional[str] = None
    S3_ACCESS_KEY: Optional[str] = None
    S3_SECRET_KEY: Optional[str] = None
    S3_USE_SSL: bool = False
    S3_REGION: str = "us-east-1"
    MAX_UPLOAD_MB: int = 25
    
    # Cost guardrails (EPIC 3)
    MAX_UPLOAD_BYTES: int = 15 * 1024 * 1024  # 15MB default
    MAX_PDF_PAGES: int = 10  # Maximum PDF pages allowed
    MAX_IMAGES: int = 20  # Maximum images allowed (for future use)
    MAX_OCR_CHARS: int = 50000  # Maximum OCR text chars sent to LLM

    # Queue backend selection
    QUEUE_BACKEND: Literal["celery"] = "celery"
    TASK_QUEUE_PROVIDER: Literal["celery", "http", "cloud_tasks"] = "celery"  # Task queue provider

    # Celery / Redis
    REDIS_URL: Optional[str] = None
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None

    # AI backend selection
    AI_BACKEND: Literal["fake", "gemini", "openai", "bedrock"] = "fake"

    # OCR provider selection
    OCR_PROVIDER: Literal["fake", "http"] = "fake"
    OCR_SERVICE_URL: Optional[str] = None  # Base URL for HTTP OCR service (e.g., "http://ocr-service:8080")

    # LLM provider selection
    LLM_PROVIDER: Literal["fake", "http"] = "fake"
    LLM_SERVICE_URL: Optional[str] = None  # Base URL for HTTP LLM service (e.g., "http://llm-service:8080")

    # GCP-specific configs
    GOOGLE_PROJECT_ID: Optional[str] = None
    GOOGLE_REGION: Optional[str] = None
    GCS_BUCKET: Optional[str] = None  # GCS bucket name
    SIGNING_SA_EMAIL: Optional[str] = None  # Service account email for GCS signed URL generation (required on Cloud Run)
    
    # Cloud Run / HTTP task queue
    PUBLIC_BASE_URL: Optional[str] = None  # Base URL for constructing callback URLs (e.g., "https://api.example.com")
    
    AWS_REGION: Optional[str] = None
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    # Chat/LLM limits
    MAX_REPLY_CHARS: int = 50000  # Maximum reply length in characters

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
