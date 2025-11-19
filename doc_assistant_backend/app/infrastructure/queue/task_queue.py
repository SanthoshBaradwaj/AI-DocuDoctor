"""Task queue abstraction - use get_task_queue() instead of this module."""
# This file is kept for backward compatibility but should not be used directly
# Use get_task_queue() from celery_queue.py instead

from app.infrastructure.queue.celery_queue import get_task_queue

# Re-export for backward compatibility (deprecated)
__all__ = ["get_task_queue"]
