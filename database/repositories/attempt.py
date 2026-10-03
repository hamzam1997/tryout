"""Attempt persistence layer using Cloud Firestore."""

from __future__ import annotations

from database.client import get_firestore_client, get_next_id
from database.documents import AttemptDoc, utc_now
from schemas import Attempt, AttemptStatus


def create_attempt(attempt: Attempt) -> Attempt:
    client = get_firestore_client()
    attempt_id = attempt.id or get_next_id("attempts")
    attempt.id = attempt_id

    doc = AttemptDoc.from_domain(attempt)
    client.collection(AttemptDoc.COLLECTION).document(str(attempt_id)).set(doc.to_doc())
    return attempt


def get_attempt(attempt_id: int) -> Attempt | None:
    client = get_firestore_client()
    doc_ref = client.collection(AttemptDoc.COLLECTION).document(str(attempt_id)).get()
    if not doc_ref.exists:
        return None
    return AttemptDoc.from_doc(doc_ref.to_dict()).to_domain()


def list_attempts(idea_id: int | None = None) -> list[Attempt]:
    client = get_firestore_client()
    query = client.collection(AttemptDoc.COLLECTION)
    if idea_id is not None:
        query = query.where("idea_id", "==", idea_id)

    docs = query.order_by("id", direction="DESCENDING").stream()
    attempts = []
    for d in docs:
        data = d.to_dict()
        if data:
            attempts.append(AttemptDoc.from_doc(data).to_domain())
    return attempts


def set_attempt_status(
    attempt_id: int, status: AttemptStatus, error: str | None = None
) -> None:
    """Advance an attempt, stamping start and finish times at the boundaries."""
    now_str = utc_now().isoformat()
    is_active = status in (
        AttemptStatus.PLANNING,
        AttemptStatus.CODING,
        AttemptStatus.TESTING,
    )
    is_terminal = status in (AttemptStatus.COMPLETE, AttemptStatus.FAILED)

    client = get_firestore_client()
    doc_ref = client.collection(AttemptDoc.COLLECTION).document(str(attempt_id))
    snap = doc_ref.get()
    if not snap.exists:
        return

    data = snap.to_dict() or {}
    payload: dict = {"status": status.value}

    if is_active or is_terminal:
        if not data.get("started_at"):
            payload["started_at"] = now_str

    if is_terminal:
        payload["finished_at"] = now_str
    else:
        payload["finished_at"] = None

    if error is not None:
        payload["error"] = error

    doc_ref.set(payload, merge=True)


def update_attempt(attempt: Attempt) -> Attempt:
    if not attempt.id:
        return create_attempt(attempt)
    client = get_firestore_client()
    doc = AttemptDoc.from_domain(attempt)
    client.collection(AttemptDoc.COLLECTION).document(str(attempt.id)).set(doc.to_doc(), merge=True)
    return attempt
