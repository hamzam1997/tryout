"""Idea persistence layer using Cloud Firestore."""

from __future__ import annotations

from database.client import get_firestore_client, get_next_id
from database.documents import AttemptDoc, FrictionLogDoc, IdeaDoc, utc_now
from schemas import Idea, IdeaStatus


def create_idea(idea: Idea) -> Idea:
    client = get_firestore_client()
    idea_id = idea.id or get_next_id("ideas")
    idea.id = idea_id

    doc = IdeaDoc.from_domain(idea)
    client.collection(IdeaDoc.COLLECTION).document(str(idea_id)).set(doc.to_doc())
    return idea


def get_idea(idea_id: int) -> Idea | None:
    client = get_firestore_client()
    doc_ref = client.collection(IdeaDoc.COLLECTION).document(str(idea_id)).get()
    if not doc_ref.exists:
        return None
    return IdeaDoc.from_doc(doc_ref.to_dict()).to_domain()


def list_ideas(
    status: IdeaStatus | None = None, meeting_id: int | None = None
) -> list[Idea]:
    client = get_firestore_client()
    query = client.collection(IdeaDoc.COLLECTION)
    if status is not None:
        query = query.where("status", "==", status.value)
    if meeting_id is not None:
        query = query.where("meeting_id", "==", meeting_id)

    docs = query.order_by("id").stream()
    ideas = []
    for d in docs:
        data = d.to_dict()
        if data:
            ideas.append(IdeaDoc.from_doc(data).to_domain())
    return ideas


def get_idea_counts() -> dict[str, int]:
    client = get_firestore_client()
    counts = {s.value: 0 for s in IdeaStatus}
    docs = client.collection(IdeaDoc.COLLECTION).stream()
    for d in docs:
        data = d.to_dict() or {}
        st = data.get("status")
        if st in counts:
            counts[st] += 1
    counts["ALL"] = sum(counts.values())
    return counts


def set_idea_status(
    idea_id: int,
    status: IdeaStatus,
    approved_by: str | None = None,
) -> Idea | None:
    client = get_firestore_client()
    doc_ref = client.collection(IdeaDoc.COLLECTION).document(str(idea_id))
    snap = doc_ref.get()
    if not snap.exists:
        return None

    now = utc_now().isoformat()
    payload = {
        "status": status.value,
        "approved_by": approved_by,
        "approved_at": now if status in (IdeaStatus.APPROVED, IdeaStatus.IN_PROCESS) else None,
    }
    doc_ref.set(payload, merge=True)
    updated = doc_ref.get().to_dict()
    return IdeaDoc.from_doc(updated).to_domain()


def approve_idea(idea_id: int, approved_by: str) -> Idea | None:
    return set_idea_status(idea_id, IdeaStatus.IN_PROCESS, approved_by=approved_by)


def reject_idea(idea_id: int) -> Idea | None:
    return set_idea_status(idea_id, IdeaStatus.REJECTED)


def find_idea_by_key(idea_key: str, meeting_id: int | None = None) -> Idea | None:
    if not idea_key:
        return None
    client = get_firestore_client()
    query = client.collection(IdeaDoc.COLLECTION).where("idea_key", "==", idea_key)
    if meeting_id is not None:
        query = query.where("meeting_id", "==", meeting_id)
    docs = list(query.stream())
    if not docs:
        return None
    return IdeaDoc.from_doc(docs[0].to_dict()).to_domain()


def update_idea(idea: Idea) -> Idea:
    if not idea.id:
        return create_idea(idea)
    client = get_firestore_client()
    doc = IdeaDoc.from_domain(idea)
    client.collection(IdeaDoc.COLLECTION).document(str(idea.id)).set(doc.to_doc(), merge=True)
    return idea


def delete_idea(idea_id: int) -> bool:
    """Delete idea and cascade delete related attempts and friction logs."""
    client = get_firestore_client()
    doc_ref = client.collection(IdeaDoc.COLLECTION).document(str(idea_id))
    if not doc_ref.get().exists:
        return False

    # Cascading attempt & friction log cleanup
    attempts = list(
        client.collection(AttemptDoc.COLLECTION).where("idea_id", "==", idea_id).stream()
    )
    for att in attempts:
        att_id = int(att.id)
        # Delete friction logs
        flogs = list(
            client.collection(FrictionLogDoc.COLLECTION).where("attempt_id", "==", att_id).stream()
        )
        for flog in flogs:
            client.collection(FrictionLogDoc.COLLECTION).document(flog.id).delete()
        client.collection(AttemptDoc.COLLECTION).document(att.id).delete()

    # Nullify original_idea_id references
    child_ideas = list(
        client.collection(IdeaDoc.COLLECTION).where("original_idea_id", "==", idea_id).stream()
    )
    for c in child_ideas:
        client.collection(IdeaDoc.COLLECTION).document(c.id).set({"original_idea_id": None}, merge=True)

    doc_ref.delete()
    return True
