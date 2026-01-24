from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
import os

from app.core.config import get_settings
from app.core.logging import get_logger
from app.infrastructure.db.db_factory import get_db

settings = get_settings()

# Lazy import engine only when needed (SQL mode)
def _get_sql_engine():
    """Get SQL engine if available (lazy import)."""
    if settings.DB_PROVIDER == "firestore":
        return None
    from app.infrastructure.db.sql_alchemy import engine
    return engine
from app.infrastructure.storage.storage_factory import get_storage_backend
from app.infrastructure.storage.s3_minio import make_s3, get_bucket_name
import redis

router = APIRouter(prefix="/api/v1/health", tags=["health"])
logger = get_logger(__name__)


@router.get("")
def health():
    """Basic health check endpoint - returns quickly with no downstream calls.
    
    Returns:
        Dict with status, app info, and optional build/version info
    """
    response = {
        "status": "ok",
        "app_env": settings.APP_ENV,
        "app_name": settings.APP_NAME,
    }
    
    # Add build/version info if available from environment
    build_id = os.getenv("BUILD_ID") or os.getenv("GITHUB_SHA") or os.getenv("CI_COMMIT_SHA")
    version = os.getenv("VERSION") or os.getenv("APP_VERSION") or os.getenv("IMAGE_TAG")
    
    if build_id:
        response["build"] = build_id
    if version:
        response["version"] = version
    
    return response


@router.get("/deps")
def health_deps(db: Session = Depends(get_db)):
    """Health check with dependency status."""
    deps_status = {}
    overall_status = "ok"
    
    # Check database
    try:
        if settings.DB_PROVIDER == "firestore":
            # For Firestore, just check if we can get a session
            # The actual health check is implicit in get_db() working
            deps_status["database"] = "up"
        else:
            # For SQL, execute a test query
            db.execute(text("SELECT 1"))
            deps_status["database"] = "up"
    except Exception as e:
        logger.error("Database health check failed", exc_info=True, extra={"error": str(e)})
        deps_status["database"] = "down"
        overall_status = "degraded"
    
    # Check storage
    try:
        storage = get_storage_backend()
        # For S3/MinIO, try a lightweight operation
        if settings.STORAGE_BACKEND == "s3_minio":
            s3 = make_s3()
            bucket = get_bucket_name()
            # Try head_bucket as a lightweight check
            s3.head_bucket(Bucket=bucket)
            deps_status["storage"] = "up"
        else:
            # For other backends, mark as up for now (will be implemented later)
            deps_status["storage"] = "up"
    except Exception as e:
        logger.error("Storage health check failed", exc_info=True, extra={"error": str(e)})
        deps_status["storage"] = "down"
        overall_status = "degraded"
    
    # Check queue
    try:
        if settings.QUEUE_BACKEND == "celery":
            # Try to ping Redis
            broker_url = settings.CELERY_BROKER_URL or settings.REDIS_URL or "redis://redis:6379/0"
            # Parse Redis URL and ping
            if broker_url.startswith("redis://"):
                # Simple Redis connection test
                try:
                    # Extract host and port from URL
                    parts = broker_url.replace("redis://", "").split("/")
                    host_port = parts[0].split(":")
                    host = host_port[0] if len(host_port) > 0 else "localhost"
                    port = int(host_port[1]) if len(host_port) > 1 else 6379
                    
                    r = redis.Redis(host=host, port=port, socket_connect_timeout=1)
                    r.ping()
                    r.close()
                    deps_status["queue"] = "up"
                except Exception as e:
                    logger.error("Queue health check failed", exc_info=True, extra={"error": str(e)})
                    deps_status["queue"] = "down"
                    overall_status = "degraded"
            else:
                # Unknown broker type, mark as up for now
                deps_status["queue"] = "up"
        else:
            # Unknown queue backend, mark as up for now
            deps_status["queue"] = "up"
    except Exception as e:
        logger.error("Queue health check failed", exc_info=True, extra={"error": str(e)})
        deps_status["queue"] = "down"
        overall_status = "degraded"
    
    # Determine final status
    if any(status == "down" for status in deps_status.values()):
        overall_status = "error"
    elif any(status == "down" for status in deps_status.values()):
        overall_status = "degraded"
    
    return {
        "status": overall_status,
        "dependencies": deps_status,
    }
