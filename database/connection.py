"""SQLAlchemy engine, session management, and connection utilities."""

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, TypeVar

from pydantic import BaseModel, TypeAdapter
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from config import settings

BUSY_TIMEOUT_MS = 5000

_db_path: Path | None = None
_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None

T = TypeVar("T", bound=BaseModel)


def set_database_path(path: Path | str | None) -> None:
    """Override the database location. Used by tests and runtime config."""
    global _db_path, _engine, _session_factory
    _db_path = Path(path) if path is not None else None
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def database_path() -> Path:
    """Return the active database file path."""
    return _db_path if _db_path is not None else settings.database_path


def get_engine() -> Engine:
    """Return or initialize the singleton SQLAlchemy Engine."""
    global _engine
    if _engine is None:
        db_file = database_path()
        db_file.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(
            f"sqlite:///{db_file}",
            connect_args={"timeout": BUSY_TIMEOUT_MS / 1000},
            echo=False,
            future=True,
        )

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
            cursor.close()

        _engine = engine
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return or initialize the sessionmaker."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            expire_on_commit=False,
        )
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager for SQLAlchemy database sessions.

    Commits upon successful block completion and rolls back on exception.
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def connect():
    """Raw DBAPI connection context manager for backward compatibility."""
    import sqlite3

    raw_conn = get_engine().raw_connection()
    dbapi_conn = getattr(raw_conn, "driver_connection", raw_conn)
    dbapi_conn.row_factory = sqlite3.Row
    try:
        yield dbapi_conn
        raw_conn.commit()
    except Exception:
        raw_conn.rollback()
        raise
    finally:
        raw_conn.close()


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def dump_model(model: BaseModel | None) -> str | None:
    """Serialize a pydantic model to a JSON string or None."""
    return model.model_dump_json() if model is not None else None


def load_model(cls: type[T], raw: str | None) -> T | None:
    """Deserialize a JSON string into a pydantic model or None."""
    return cls.model_validate_json(raw) if raw else None


def dump_model_list(models: list[T]) -> str:
    """Serialize a list of pydantic models to a JSON string."""
    return json.dumps([m.model_dump(mode="json") for m in models])


def load_model_list(cls: type[T], raw: str | None) -> list[T]:
    """Deserialize a JSON string into a list of pydantic models."""
    if not raw:
        return []
    adapter = TypeAdapter(list[cls])
    return adapter.validate_json(raw)
