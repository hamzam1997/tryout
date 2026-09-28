"""SQLAlchemy database schema initialization."""

from sqlalchemy import inspect, text

from database.connection import database_path, get_engine
from database.models import Base


def _idea_schema_is_current(engine) -> bool:
    """True when the idea table already matches the renamed columns."""
    inspector = inspect(engine)
    if "idea" not in inspector.get_table_names():
        return True
    columns = {col["name"] for col in inspector.get_columns("idea")}
    required = {
        "quote",
        "cue_time",
        "priority",
        "attempt_hypothesis",
        "catalog_refs_json",
        "idea_key",
        "original_idea_id",
        "approved_by",
        "approved_at",
    }
    return required.issubset(columns)


def _recreate_idea_dependent_tables(engine) -> None:
    """Drop idea and dependent tables so create_all can rebuild the new shape.

    Safe for the hackathon SQLite workflow: local idea/attempt/friction data is
    regenerable. Meeting and repository rows are preserved.
    """
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        for table in ("friction_log", "attempt", "idea"):
            conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
        conn.execute(text("PRAGMA foreign_keys=ON"))
        conn.commit()


def _ensure_meeting_ideas_error_column(engine) -> None:
    """Add meeting.ideas_error on existing SQLite DBs without dropping meetings."""
    inspector = inspect(engine)
    if "meeting" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("meeting")}
    if "ideas_error" in columns:
        return
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE meeting ADD COLUMN ideas_error TEXT"))
        conn.commit()


def init_db() -> None:
    """Create tables and indexes via SQLAlchemy metadata and ensure WAL mode."""
    database_path().parent.mkdir(parents=True, exist_ok=True)
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.commit()
    if not _idea_schema_is_current(engine):
        _recreate_idea_dependent_tables(engine)
    Base.metadata.create_all(bind=engine)
    _ensure_meeting_ideas_error_column(engine)
