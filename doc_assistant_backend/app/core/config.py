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
    DATABASE_URL: AnyUrl

    # Storage backend selection
    STORAGE_BACKEND: Literal["s3_minio", "gcs", "s3_aws"] = "s3_minio"

    # Storage (S3/MinIO) settings for local
    S3_ENDPOINT: Optional[str] = None
    S3_BUCKET: Optional[str] = None
    S3_ACCESS_KEY: Optional[str] = None
    S3_SECRET_KEY: Optional[str] = None
    S3_USE_SSL: bool = False
    S3_REGION: str = "us-east-1"
    MAX_UPLOAD_MB: int = 25

    # Queue backend selection
    QUEUE_BACKEND: Literal["celery"] = "celery"

    # Celery / Redis
    REDIS_URL: Optional[str] = None
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None

    # AI backend selection
    AI_BACKEND: Literal["fake", "gemini", "openai", "bedrock"] = "fake"

    # Placeholders for future cloud-specific configs
    GOOGLE_PROJECT_ID: Optional[str] = None
    GOOGLE_REGION: Optional[str] = None
    AWS_REGION: Optional[str] = None
    
    # Logging
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
