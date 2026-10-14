"""Repository persistence layer using Cloud Firestore."""

from __future__ import annotations

from database.client import get_firestore_client, get_next_id
from database.scope import exists, scoped
from database.documents import RepositoryDoc, utc_now
from schemas import ArchitectureCatalog, Repository


def create_repository(repo: Repository) -> Repository:
    client = get_firestore_client()
    repo_id = repo.id or get_next_id("repositories")
    repo.id = repo_id

    doc = RepositoryDoc.from_domain(repo)
    client.collection(RepositoryDoc.COLLECTION).document(str(repo_id)).set(doc.to_doc())
    return repo


def get_repository(repo_id: int) -> Repository | None:
    client = get_firestore_client()
    doc_ref = client.collection(RepositoryDoc.COLLECTION).document(str(repo_id)).get()
    if not exists(doc_ref):
        return None
    doc = RepositoryDoc.from_doc(doc_ref.to_dict())
    return doc.to_domain()


def get_repository_by_source(source: str) -> Repository | None:
    client = get_firestore_client()
    query = scoped(client.collection(RepositoryDoc.COLLECTION)).where("source", "==", source)
    docs = list(query.stream())
    if not docs:
        return None
    doc = RepositoryDoc.from_doc(docs[0].to_dict())
    return doc.to_domain()


def list_repositories() -> list[Repository]:
    client = get_firestore_client()
    docs = scoped(client.collection(RepositoryDoc.COLLECTION)).stream()
    result = []
    for d in docs:
        data = d.to_dict()
        if data:
            result.append(RepositoryDoc.from_doc(data).to_domain())
    result.sort(key=lambda r: r.id)
    return result


def get_or_create_repository(repo: Repository) -> Repository:
    existing = get_repository_by_source(repo.source)
    return existing if existing else create_repository(repo)


def update_repository(repo: Repository) -> Repository:
    if not repo.id:
        return create_repository(repo)
    client = get_firestore_client()
    doc = RepositoryDoc.from_domain(repo)
    client.collection(RepositoryDoc.COLLECTION).document(str(repo.id)).set(doc.to_doc(), merge=True)
    return repo


def save_catalog(
    repo_id: int, catalog: ArchitectureCatalog, source_ref: str | None = None
) -> None:
    """Cache a generated catalog against the repo state it was built from."""
    client = get_firestore_client()
    now_str = utc_now().isoformat()
    client.collection(RepositoryDoc.COLLECTION).document(str(repo_id)).set(
        {
            "catalog": catalog.model_dump(mode="json"),
            "catalog_generated_at": now_str,
            "catalog_status": "ready",
            "catalog_error": None,
            "source_ref": source_ref,
        },
        merge=True,
    )


def catalog_is_current(repo_or_id: int | Repository, current_commit: str) -> bool:
    """True if the cached catalog was built from current_commit."""
    if isinstance(repo_or_id, Repository):
        repo = repo_or_id
    else:
        repo = get_repository(repo_or_id)
    if not repo or not repo.catalog:
        return False
    return repo.source_ref == current_commit


def set_repository_status(
    repo_id: int, status: str, error: str | None = None
) -> None:
    """Update catalog onboarding status and optional error message."""
    client = get_firestore_client()
    payload = {"catalog_status": status, "catalog_error": error}
    client.collection(RepositoryDoc.COLLECTION).document(str(repo_id)).set(payload, merge=True)


def delete_repository(repo_id: int) -> bool:
    """Delete a repository document from Firestore."""
    client = get_firestore_client()
    doc_ref = client.collection(RepositoryDoc.COLLECTION).document(str(repo_id))
    if not exists(doc_ref.get()):
        return False
    doc_ref.delete()
    return True
