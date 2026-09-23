"""SQLite connection and transaction management."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, TypeVar

from pydantic import BaseModel, TypeAdapter

from config import settings

BUSY_TIMEOUT_MS = 5000

_db_path: Path | None = None
T = TypeVar("T", bound=BaseModel)


def set_database_path(path: Path | str | None) -> None:
    """Override the database location. Used by tests and runtime config."""
    global _db_path
    _db_path = Path(path) if path is not None else None


def database_path() -> Path:
    """Return the active database file path."""
    return _db_path if _db_path is not None else settings.database_path


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


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


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Open an isolated SQLite connection.

    Enables foreign keys and busy timeout per connection. Commits on exit,
    rolls back on unhandled error, and closes cleanly.
    """
    conn = sqlite3.connect(database_path(), timeout=BUSY_TIMEOUT_MS / 1000)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
