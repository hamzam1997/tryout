"""Meeting ingestion endpoints."""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request

import database as db
from agents.idea_extractor import IdeaExtractorError, extract_ideas
from agents.note_taker import NoteTakerError, ingest, take_notes
from agents.transcript import TranscriptError
from config import BASE_DIR
from schemas import MeetingSource, MeetingStatus

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


def _run_idea_extraction(meeting_id: int) -> tuple[list, str | None]:
    """Extract ideas and persist success/failure on the meeting row."""
    try:
        ideas = extract_ideas(meeting_id)
    except IdeaExtractorError as exc:
        db.set_meeting_ideas_error(meeting_id, str(exc))
        return [], str(exc)

    db.set_meeting_ideas_error(meeting_id, None)
    return ideas, None


@bp.post("/upload")
def upload_meeting():
    """Ingest a .vtt/.srt/.txt transcript, then generate minutes.

    The meeting row is committed before the model runs, so a Gemini failure
    returns 502 with the transcript already stored and the meeting FAILED.
    Idea extraction is best-effort: failures are stored on meeting.ideas_error.
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
        meeting, parsed = ingest(
            raw,
            title=title,
            filename=filename,
            source=MeetingSource.UPLOAD,
            occurred_at=occurred_at,
        )
    except TranscriptError as exc:
        return jsonify({"error": str(exc)}), 400

    payload = {
        "meeting": _serialise(meeting),
        "speakers": parsed.speakers,
        "cue_count": len(parsed.cues),
        "format": parsed.source_format.value,
    }

    try:
        meeting = take_notes(meeting.id)
    except NoteTakerError as exc:
        payload["meeting"] = _serialise(db.get_meeting(meeting.id))
        payload["error"] = str(exc)
        return jsonify(payload), 502

    ideas, ideas_error = _run_idea_extraction(meeting.id)
    meeting = db.get_meeting(meeting.id)
    payload["meeting"] = _serialise(meeting)
    payload["ideas"] = [idea.model_dump(mode="json") for idea in ideas]
    if ideas_error:
        payload["ideas_error"] = ideas_error

    return jsonify(payload), 201


@bp.post("/demo")
def load_demo_meeting():
    """Ingest the bundled weekly-ops demo transcript, then extract ideas."""
    fixture_path = BASE_DIR / "fixtures" / "meetings" / "2026-09-17-weekly-ops.vtt"
    if not fixture_path.is_file():
        return jsonify({"error": "Demo meeting transcript not found"}), 404
    raw = fixture_path.read_text(encoding="utf-8")
    title = "Weekly Ops Sync (Acme Store Demo)"

    meeting, parsed = ingest(
        raw,
        title=title,
        filename="2026-09-17-weekly-ops.vtt",
        source=MeetingSource.SEED,
        occurred_at=datetime(2026, 9, 17, 10, 0),
    )
    payload = {
        "meeting": _serialise(meeting),
        "speakers": parsed.speakers,
        "cue_count": len(parsed.cues),
        "format": parsed.source_format.value,
    }
    try:
        meeting = take_notes(meeting.id)
    except NoteTakerError as exc:
        payload["meeting"] = _serialise(db.get_meeting(meeting.id))
        payload["error"] = str(exc)
        return jsonify(payload), 502

    ideas, ideas_error = _run_idea_extraction(meeting.id)
    meeting = db.get_meeting(meeting.id)
    payload["meeting"] = _serialise(meeting)
    payload["ideas"] = [idea.model_dump(mode="json") for idea in ideas]
    if ideas_error:
        payload["ideas_error"] = ideas_error

    return jsonify(payload), 201


@bp.post("/<int:meeting_id>/extract-ideas")
def retry_extract_ideas(meeting_id: int):
    """Re-run idea extraction for a meeting that already has minutes."""
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

    ideas, ideas_error = _run_idea_extraction(meeting_id)
    meeting = db.get_meeting(meeting_id)
    payload = {
        "meeting": _serialise(meeting),
        "ideas": [idea.model_dump(mode="json") for idea in ideas],
    }
    if ideas_error:
        payload["ideas_error"] = ideas_error
        return jsonify(payload), 502
    return jsonify(payload)


@bp.get("")
def list_meetings():
    return jsonify([_serialise(m) for m in db.list_meetings()])


@bp.get("/<int:meeting_id>")
def get_meeting(meeting_id: int):
    meeting = db.get_meeting(meeting_id)
    if meeting is None:
        return jsonify({"error": "meeting not found"}), 404
    return jsonify(_serialise(meeting))
