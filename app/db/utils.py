from contextlib import contextmanager
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)

@contextmanager
def managed_transaction(session: Session):
    """
    Context manager for safely handling database transactions.
    Commits on success, rolls back on any exception, and ensures the session is closed.
    """
    try:
        yield session
        session.commit()
        logger.debug("Transaction committed successfully.")
    except Exception as e:
        logger.error(f"Transaction failed. Rolling back. Error: {e}", exc_info=True)
        session.rollback()
        raise
    finally:
        # Closing the session is typically handled by the dependency injection system
        # in a web app context, but explicit closing can be useful in scripts.
        # For now, we'll leave it to the session provider (e.g., FastAPI's dependency).
        pass
