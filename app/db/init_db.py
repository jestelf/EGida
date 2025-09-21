from app.db.base import Base
from app.db.session import engine


def init_database() -> None:
    """Create database tables if they do not yet exist."""

    # Import models to ensure they are registered with SQLAlchemy metadata.
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
