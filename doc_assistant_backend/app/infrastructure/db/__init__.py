# Database infrastructure module
# Note: Do not import sql_alchemy eagerly to avoid engine creation when using Firestore.
# Import from sql_alchemy directly when needed, or use db_factory.get_db() for database sessions.

from .models import User, Document

__all__ = ["User", "Document"]

