"""Meeting ingestion endpoints."""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request

import database as db
from agents.idea_jobs import on_minutes_ready
from agents.meeting_jobs import queue_minutes
from agents.note_taker import ingest
from agents.transcript import TranscriptError
from config import BASE_DIR
from schemas import IdeasExtractStatus, MeetingSource, MeetingStatus

bp = Blueprint("meetings", __name__, url_prefix="/meetings")

ALLOWED_SUFFIXES = (".vtt", ".srt", ".txt")
MAX_TRANSCRIPT_BYTES = 2 * 1024 * 1024


def _parse_occurred_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("occurred_at must be ISO-8601") from exc


def _serialise(meeting) -> dict:
    return meeting.model_dump(mode="json")


def _meeting_payload(meeting, parsed, *, queued: bool, duplicate: bool = False) -> dict:
    if duplicate and not queued:
        message = "This transcript was already uploaded; reusing the existing meeting."
    elif queued:
        message = "Meeting stored; minutes and ideas are processing in the background."
    else:
        message = "Meeting accepted."
    return {
        "meeting": _serialise(meeting),
        "speakers": parsed.speakers,
        "cue_count": len(parsed.cues),
        "format": parsed.source_format.value,
        "minutes_queued": queued,
        "duplicate": duplicate,
        "message": message,
    }


def _accept_meeting(meeting, parsed, *, created: bool):
    """Queue minutes only for new or failed meetings; never duplicate rows."""
    should_queue = created or meeting.status == MeetingStatus.FAILED
    if should_queue and meeting.status != MeetingStatus.PROCESSING:
        queue_minutes(meeting.id)
        meeting = db.get_meeting(meeting.id)
        return jsonify(_meeting_payload(meeting, parsed, queued=True, duplicate=not created)), 202

    return (
        jsonify(_meeting_payload(meeting, parsed, queued=False, duplicate=not created)),
        200 if not created else 202,
    )


@bp.post("/upload")
def upload_meeting():
    """Persist a transcript and queue minutes (then ideas) in the background.

    Identical transcripts reuse the existing meeting row.
    """
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify({"error": "a transcript file is required"}), 400

    filename = uploaded.filename
    if not filename.lower().endswith(ALLOWED_SUFFIXES):
        return jsonify(
            {"error": f"unsupported file type; expected one of {ALLOWED_SUFFIXES}"}
        ), 400

    blob = uploaded.read()
    if len(blob) > MAX_TRANSCRIPT_BYTES:
        return jsonify({"error": "transcript exceeds 2MB"}), 413
    try:
        raw = blob.decode("utf-8")
    except UnicodeDecodeError:
        return jsonify({"error": "transcript must be UTF-8"}), 400

    title = (request.form.get("title") or "").strip() or filename.rsplit(".", 1)[0]
    try:
        occurred_at = _parse_occurred_at(request.form.get("occurred_at"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        meeting, parsed, created = ingest(
            raw,
            title=title,
            filename=filename,
            source=MeetingSource.UPLOAD,
            occurred_at=occurred_at,
        )
    except TranscriptError as exc:
        return jsonify({"error": str(exc)}), 400

    return _accept_meeting(meeting, parsed, created=created)


@bp.post("/demo")
def load_demo_meeting():
    """Ingest the bundled weekly-ops demo transcript; minutes/ideas run in background."""
    fixture_path = BASE_DIR / "fixtures" / "meetings" / "2026-09-17-weekly-ops.vtt"
    if not fixture_path.is_file():
        return jsonify({"error": "Demo meeting transcript not found"}), 404
    raw = fixture_path.read_text(encoding="utf-8")
    title = "Weekly Ops Sync (Acme Store Demo)"

    meeting, parsed, created = ingest(
        raw,
        title=title,
        filename="2026-09-17-weekly-ops.vtt",
        source=MeetingSource.SEED,
        occurred_at=datetime(2026, 9, 17, 10, 0),
    )
    return _accept_meeting(meeting, parsed, created=created)


@bp.post("/<int:meeting_id>/extract-ideas")
def retry_extract_ideas(meeting_id: int):
    """Queue another background idea-extraction pass for a processed meeting."""
    meeting = db.get_meeting(meeting_id)
    if meeting is None:
        return jsonify({"error": "meeting not found"}), 404
    if meeting.status != MeetingStatus.PROCESSED:
        return jsonify(
            {
                "error": (
                    "idea extraction requires PROCESSED minutes "
                    f"(current: {meeting.status.value})"
                )
            }
        ), 409
    if meeting.ideas_status == IdeasExtractStatus.PROCESSING:
        return jsonify(
            {
                "meeting": _serialise(meeting),
                "ideas_queued": True,
                "message": "idea extraction already in progress",
            }
        ), 202

    on_minutes_ready(meeting_id)
    meeting = db.get_meeting(meeting_id)
    return jsonify({"meeting": _serialise(meeting), "ideas_queued": True}), 202


@bp.get("")
def list_meetings():
    return jsonify([_serialise(m) for m in db.list_meetings()])


@bp.get("/<int:meeting_id>")
def get_meeting(meeting_id: int):
    meeting = db.get_meeting(meeting_id)
    if meeting is None:
        return jsonify({"error": "meeting not found"}), 404
    return jsonify(_serialise(meeting))


@bp.delete("/<int:meeting_id>")
def delete_meeting(meeting_id: int):
    """Delete a meeting and its cascaded ideas/attempts."""
    if not db.delete_meeting(meeting_id):
        return jsonify({"error": "meeting not found"}), 404
    return "", 204
