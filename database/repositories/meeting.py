"""Meeting persistence layer using Cloud Firestore."""

from __future__ import annotations

from database.client import get_firestore_client, get_next_id
from database.scope import exists, scoped, stamped
from database.documents import IdeaDoc, MeetingDoc
from schemas import (
    IdeasExtractStatus,
    Meeting,
    MeetingStatus,
)


import logging

logger = logging.getLogger(__name__)


def create_meeting(meeting: Meeting) -> Meeting:
    client = get_firestore_client()
    meeting_id = meeting.id or get_next_id("meetings")
    meeting.id = meeting_id

    doc = MeetingDoc.from_domain(meeting)
    client.collection(MeetingDoc.COLLECTION).document(str(meeting_id)).set(stamped(doc.to_doc()))
    return meeting


def get_meeting(meeting_id: int) -> Meeting | None:
    client = get_firestore_client()
    doc_ref = client.collection(MeetingDoc.COLLECTION).document(str(meeting_id)).get()
    if not exists(doc_ref):
        return None
    doc = MeetingDoc.from_doc(doc_ref.to_dict())
    return doc.to_domain()


def find_meeting_by_external_id(external_id: str) -> Meeting | None:
    """Return the earliest meeting with this external_id (transcript fingerprint)."""
    if not external_id:
        return None
    client = get_firestore_client()
    try:
        docs = list(
            scoped(client.collection(MeetingDoc.COLLECTION))
            .where("external_id", "==", external_id)
            .stream()
        )
        if not docs:
            return None
        docs.sort(key=lambda d: d.to_dict().get("id", 0))
        return MeetingDoc.from_doc(docs[0].to_dict()).to_domain()
    except Exception as exc:
        logger.warning("Could not query meeting by external_id: %s", exc)
        return None


def find_meeting_by_transcript(transcript: str) -> Meeting | None:
    """Return the earliest meeting with an exact transcript match (legacy rows)."""
    if not transcript or len(transcript.encode("utf-8")) > 1400:
        return None
    client = get_firestore_client()
    try:
        docs = list(
            scoped(client.collection(MeetingDoc.COLLECTION))
            .where("transcript", "==", transcript)
            .stream()
        )
        if not docs:
            return None
        docs.sort(key=lambda d: d.to_dict().get("id", 0))
        return MeetingDoc.from_doc(docs[0].to_dict()).to_domain()
    except Exception as exc:
        logger.warning("Could not query meeting by transcript: %s", exc)
        return None


def list_meetings() -> list[Meeting]:
    client = get_firestore_client()
    docs = scoped(client.collection(MeetingDoc.COLLECTION)).stream()
    meetings = []
    for d in docs:
        data = d.to_dict()
        if data:
            meetings.append(MeetingDoc.from_doc(data).to_domain())

    # Sort in memory: occurred_at or created_at descending
    def sort_key(m: Meeting):
        ts = m.occurred_at or m.created_at
        return ts.isoformat() if ts else ""

    meetings.sort(key=sort_key, reverse=True)
    return meetings


def update_meeting(meeting: Meeting) -> Meeting:
    if not meeting.id:
        return create_meeting(meeting)
    client = get_firestore_client()
    doc = MeetingDoc.from_domain(meeting)
    client.collection(MeetingDoc.COLLECTION).document(str(meeting.id)).set(doc.to_doc(), merge=True)
    return meeting


def set_meeting_status(meeting_id: int, status: MeetingStatus) -> None:
    client = get_firestore_client()
    client.collection(MeetingDoc.COLLECTION).document(str(meeting_id)).set(
        {"status": status.value}, merge=True
    )


def set_meeting_ideas_state(
    meeting_id: int, state: IdeasExtractStatus, ideas_error: str | None = None
) -> None:
    client = get_firestore_client()
    payload: dict = {"ideas_status": state.value}
    if ideas_error is not None:
        payload["ideas_error"] = ideas_error
    elif state == IdeasExtractStatus.PROCESSED:
        payload["ideas_error"] = None
    client.collection(MeetingDoc.COLLECTION).document(str(meeting_id)).set(
        payload, merge=True
    )


def set_meeting_ideas_error(meeting_id: int, error: str | None) -> None:
    client = get_firestore_client()
    client.collection(MeetingDoc.COLLECTION).document(str(meeting_id)).set(
        {"ideas_error": error}, merge=True
    )


def delete_meeting(meeting_id: int) -> bool:
    """Delete meeting and cascade delete its ideas from Firestore."""
    client = get_firestore_client()
    doc_ref = client.collection(MeetingDoc.COLLECTION).document(str(meeting_id))
    if not exists(doc_ref.get()):
        return False

    # Cascade delete ideas belonging to this meeting
    idea_docs = list(
        scoped(client.collection(IdeaDoc.COLLECTION)).where("meeting_id", "==", meeting_id).stream()
    )
    for idoc in idea_docs:
        client.collection(IdeaDoc.COLLECTION).document(idoc.id).delete()

    doc_ref.delete()
    return True
