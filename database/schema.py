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
    is_sqlite = engine.dialect.name == "sqlite"
    with engine.connect() as conn:
        if is_sqlite:
            conn.execute(text("PRAGMA foreign_keys=OFF"))
        for table in ("friction_log", "attempt", "idea"):
            if engine.dialect.name == "postgresql":
                conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
            else:
                conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
        if is_sqlite:
            conn.execute(text("PRAGMA foreign_keys=ON"))
        conn.commit()


def _ensure_meeting_columns(engine) -> None:
    """Ensure all required columns exist in meeting table."""
    inspector = inspect(engine)
    if "meeting" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("meeting")}
    timestamp_type = "DATETIME" if engine.dialect.name == "sqlite" else "TIMESTAMP"
    with engine.connect() as conn:
        if "status" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE meeting ADD COLUMN status "
                    "VARCHAR(32) DEFAULT 'pending' NOT NULL"
                )
            )
        if "ideas_error" not in columns:
            conn.execute(text("ALTER TABLE meeting ADD COLUMN ideas_error TEXT"))
        if "ideas_status" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE meeting ADD COLUMN ideas_status "
                    "VARCHAR(32) NOT NULL DEFAULT 'PENDING'"
                )
            )
        if "external_source" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE meeting ADD COLUMN external_source "
                    "VARCHAR(64) DEFAULT 'paste' NOT NULL"
                )
            )
        if "external_id" not in columns:
            conn.execute(
                text("ALTER TABLE meeting ADD COLUMN external_id VARCHAR(256)")
            )
        if "external_url" not in columns:
            conn.execute(text("ALTER TABLE meeting ADD COLUMN external_url TEXT"))
        if "occurred_at" not in columns:
            conn.execute(
                text(f"ALTER TABLE meeting ADD COLUMN occurred_at {timestamp_type}")
            )
        conn.commit()


def _ensure_repository_status_columns(engine) -> None:
    """Add repository.catalog_status and catalog_error on existing DBs."""
    inspector = inspect(engine)
    if "repository" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("repository")}
    timestamp_type = "DATETIME" if engine.dialect.name == "sqlite" else "TIMESTAMP"
    with engine.connect() as conn:
        if "catalog_status" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE repository ADD COLUMN catalog_status "
                    "VARCHAR(32) DEFAULT 'ready' NOT NULL"
                )
            )
        if "catalog_error" not in columns:
            conn.execute(text("ALTER TABLE repository ADD COLUMN catalog_error TEXT"))
        if "catalog_generated_at" not in columns:
            conn.execute(
                text(
                    f"ALTER TABLE repository ADD COLUMN catalog_generated_at {timestamp_type}"
                )
            )
        conn.commit()


def init_db() -> None:
    """Create tables and indexes via SQLAlchemy metadata."""
    engine = get_engine()
    if engine.dialect.name == "sqlite":
        db_file = database_path()
        db_file.parent.mkdir(parents=True, exist_ok=True)
        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.commit()
    if not _idea_schema_is_current(engine):
        _recreate_idea_dependent_tables(engine)
    Base.metadata.create_all(bind=engine)
    _ensure_meeting_columns(engine)
    _ensure_repository_status_columns(engine)
