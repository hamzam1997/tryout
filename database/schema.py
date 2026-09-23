"""SQLAlchemy database schema initialization."""

from sqlalchemy import text

from database.connection import database_path, get_engine
from database.orm import Base

SCHEMA = """
-- Managed by SQLAlchemy 2.0 DeclarativeBase (database.orm.Base)
-- Tables: repository, meeting, idea, attempt, friction_log
"""


def init_db() -> None:
    """Create tables and indexes via SQLAlchemy metadata and ensure WAL mode."""
    database_path().parent.mkdir(parents=True, exist_ok=True)
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
