"""Attempt persistence layer using Cloud Firestore."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from database.client import get_firestore_client, get_next_id
from database.scope import exists, scoped
from database.documents import AttemptDoc, utc_now
from schemas import Attempt, AttemptStatus

_IN_FLIGHT = {
    AttemptStatus.QUEUED,
    AttemptStatus.PLANNING,
    AttemptStatus.CODING,
    AttemptStatus.TESTING,
}
# A live attempt logs an event every tool call; this much silence means its worker died
# (instance recycled or crashed), so it would otherwise show as running forever.
STALE_AFTER = timedelta(minutes=15)
STALE_ERROR = "The attempt stopped responding (its worker was restarted). Retry to run it again."


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _expire_if_stale(attempt: Attempt) -> Attempt:
    """Fail an in-flight attempt whose worker has gone silent, so it can be retried."""
    if attempt.status not in _IN_FLIGHT:
        return attempt
    moments = [step.timestamp for step in attempt.events]
    moments += [m for m in (attempt.started_at, attempt.created_at) if m]
    if not moments or utc_now() - max(_aware(m) for m in moments) < STALE_AFTER:
        return attempt
    set_attempt_status(attempt.id, AttemptStatus.FAILED, error=STALE_ERROR)
    return attempt.model_copy(update={"status": AttemptStatus.FAILED, "error": STALE_ERROR})


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
    if not exists(doc_ref):
        return None
    return _expire_if_stale(AttemptDoc.from_doc(doc_ref.to_dict()).to_domain())


def list_attempts(idea_id: int | None = None) -> list[Attempt]:
    client = get_firestore_client()
    query = scoped(client.collection(AttemptDoc.COLLECTION))
    if idea_id is not None:
        query = query.where("idea_id", "==", idea_id)

    docs = query.stream()
    attempts = []
    for d in docs:
        data = d.to_dict()
        if data:
            attempts.append(_expire_if_stale(AttemptDoc.from_doc(data).to_domain()))
    attempts.sort(key=lambda x: x.id, reverse=True)
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
    is_terminal = status in (
        AttemptStatus.READY_FOR_REVIEW,
        AttemptStatus.COMPLETE,
        AttemptStatus.FAILED,
    )

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
