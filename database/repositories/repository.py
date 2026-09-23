"""Repository persistence layer for codebase repositories."""

import sqlite3

from database.connection import (
    connect,
    dump_model,
    load_model,
    utc_now_iso,
)
from database.models import ArchitectureCatalog, RepoSource, Repository


def row_to_repository(row: sqlite3.Row) -> Repository:
    return Repository(
        id=row["id"],
        name=row["name"],
        source=row["source"],
        source_type=RepoSource(row["source_type"]),
        source_ref=row["source_ref"],
        catalog=load_model(ArchitectureCatalog, row["catalog_json"]),
        catalog_generated_at=row["catalog_generated_at"],
        created_at=row["created_at"],
    )


def create_repository(repo: Repository) -> Repository:
    created_at = repo.created_at or utc_now_iso()
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO repository
               (name, source, source_type, source_ref, catalog_json,
                catalog_generated_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                repo.name,
                repo.source,
                repo.source_type.value,
                repo.source_ref,
                dump_model(repo.catalog),
                repo.catalog_generated_at,
                created_at,
            ),
        )
        return repo.model_copy(update={"id": cur.lastrowid, "created_at": created_at})


def get_repository(repo_id: int) -> Repository | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM repository WHERE id = ?", (repo_id,)
        ).fetchone()
    return row_to_repository(row) if row else None


def get_repository_by_source(source: str) -> Repository | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM repository WHERE source = ?", (source,)
        ).fetchone()
    return row_to_repository(row) if row else None


def list_repositories() -> list[Repository]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM repository ORDER BY id").fetchall()
    return [row_to_repository(row) for row in rows]


def get_or_create_repository(repo: Repository) -> Repository:
    existing = get_repository_by_source(repo.source)
    return existing if existing else create_repository(repo)


def update_repository(repo: Repository) -> Repository:
    with connect() as conn:
        conn.execute(
            """UPDATE repository
               SET name = ?, source = ?, source_type = ?, source_ref = ?,
                   catalog_json = ?, catalog_generated_at = ?
               WHERE id = ?""",
            (
                repo.name,
                repo.source,
                repo.source_type.value,
                repo.source_ref,
                dump_model(repo.catalog),
                repo.catalog_generated_at,
                repo.id,
            ),
        )
    return repo


def save_catalog(
    repo_id: int, catalog: ArchitectureCatalog, source_ref: str | None = None
) -> None:
    """Cache a generated catalog against the repo state it was built from."""
    with connect() as conn:
        conn.execute(
            """UPDATE repository
               SET catalog_json = ?, catalog_generated_at = ?, source_ref = ?
               WHERE id = ?""",
            (catalog.model_dump_json(), utc_now_iso(), source_ref, repo_id),
        )


def catalog_is_current(repo: Repository, source_ref: str | None) -> bool:
    """True when a cached catalog exists and the repo has not moved since."""
    return (
        repo.catalog is not None
        and repo.source_ref is not None
        and repo.source_ref == source_ref
    )
