"""Repository persistence layer for codebase repositories using SQLAlchemy."""

from sqlalchemy import select

from database.connection import (
    dump_model,
    load_model,
    session_scope,
    utc_now,
)
from database.models import Repository as RepositoryModel
from schemas import ArchitectureCatalog, RepoSource, Repository


def orm_to_repository(orm: RepositoryModel) -> Repository:
    return Repository(
        id=orm.id,
        name=orm.name,
        source=orm.source,
        source_type=RepoSource(orm.source_type),
        source_ref=orm.source_ref,
        catalog=load_model(ArchitectureCatalog, orm.catalog_json),
        catalog_status=getattr(orm, "catalog_status", "ready"),
        catalog_error=getattr(orm, "catalog_error", None),
        catalog_generated_at=orm.catalog_generated_at,
        created_at=orm.created_at,
    )


def create_repository(repo: Repository) -> Repository:
    created_at = repo.created_at or utc_now()
    with session_scope() as session:
        model = RepositoryModel(
            name=repo.name,
            source=repo.source,
            source_type=repo.source_type.value,
            source_ref=repo.source_ref,
            catalog_json=dump_model(repo.catalog),
            catalog_status=repo.catalog_status,
            catalog_error=repo.catalog_error,
            catalog_generated_at=repo.catalog_generated_at,
            created_at=created_at,
        )
        session.add(model)
        session.flush()
        saved = orm_to_repository(model)

    try:
        from database.gcs_sync import backup_db_to_gcs_async
        backup_db_to_gcs_async()
    except Exception:
        pass

    return saved


def get_repository(repo_id: int) -> Repository | None:
    with session_scope() as session:
        model = session.get(RepositoryModel, repo_id)
        return orm_to_repository(model) if model else None


def get_repository_by_source(source: str) -> Repository | None:
    with session_scope() as session:
        stmt = select(RepositoryModel).where(RepositoryModel.source == source)
        model = session.scalars(stmt).first()
        return orm_to_repository(model) if model else None


def list_repositories() -> list[Repository]:
    with session_scope() as session:
        stmt = select(RepositoryModel).order_by(RepositoryModel.id)
        models = session.scalars(stmt).all()
        return [orm_to_repository(m) for m in models]


def get_or_create_repository(repo: Repository) -> Repository:
    existing = get_repository_by_source(repo.source)
    return existing if existing else create_repository(repo)


def update_repository(repo: Repository) -> Repository:
    with session_scope() as session:
        model = session.get(RepositoryModel, repo.id)
        if model:
            model.name = repo.name
            model.source = repo.source
            model.source_type = repo.source_type.value
            model.source_ref = repo.source_ref
            model.catalog_json = dump_model(repo.catalog)
            model.catalog_generated_at = repo.catalog_generated_at
    return repo


def save_catalog(
    repo_id: int, catalog: ArchitectureCatalog, source_ref: str | None = None
) -> None:
    """Cache a generated catalog against the repo state it was built from."""
    with session_scope() as session:
        model = session.get(RepositoryModel, repo_id)
        if model:
            model.catalog_json = catalog.model_dump_json()
            model.catalog_generated_at = utc_now()
            model.catalog_status = "ready"
            model.catalog_error = None
            model.source_ref = source_ref

    try:
        from database.gcs_sync import backup_db_to_gcs_async
        backup_db_to_gcs_async()
    except Exception:
        pass


def set_repository_status(
    repo_id: int, status: str, error: str | None = None
) -> None:
    """Update onboarding catalog status ('onboarding', 'ready', 'failed')."""
    with session_scope() as session:
        model = session.get(RepositoryModel, repo_id)
        if model:
            model.catalog_status = status
            model.catalog_error = error

    try:
        from database.gcs_sync import backup_db_to_gcs_async
        backup_db_to_gcs_async()
    except Exception:
        pass


def catalog_is_current(repo: Repository, source_ref: str | None) -> bool:
    """True when a cached catalog exists and the repo has not moved since."""
    return (
        repo.catalog is not None
        and repo.source_ref is not None
        and repo.source_ref == source_ref
    )
