"""Note taker agent: transcript in, meeting minutes out.

Ingestion writes the meeting row before calling Gemini, so a model failure
costs a retry rather than the upload. Meeting.status records which of those
happened.
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime

from google.genai import types

import database as db
from agents.transcript import ParsedTranscript, parse_transcript
from config import settings
from llm import get_client
from logging_setup import log_event
from schemas import Meeting, MeetingMinutes, MeetingSource, MeetingStatus

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """\
You are a note taker for engineering and operations meetings.

You are given a multi-speaker transcript. Each line is formatted as
"[HH:MM:SS] Speaker: text". Some lines may have no timestamp or no speaker.

Produce:
- summary: a short executive summary, 2-4 sentences, plain prose.
- key_points: the substantive discussion points. Attribute them to the
  speaker who made them where attribution is clear.
- action_items: everything the meeting surfaced as work someone could
  actually do. Include firm commitments, proposals, plans, and nice-to-haves
  that nobody owned yet - if a person floated it as worth doing, capture it.
  Name the owner when the transcript identifies one, and leave it unowned
  otherwise rather than guessing. Exclude status updates, things already
  finished, and scheduling or availability notes.

  A suggestion is its own item even when nobody agreed to it and even when
  someone was assigned to investigate it. "Can we automatically do X?"
  followed by "I'll look into it" is two items, not one: the thing to build,
  and the investigation.

Report only what the transcript supports. Do not speculate about intent, and
do not carry over knowledge from outside the transcript.\
"""


class NoteTakerError(RuntimeError):
    """Raised when minutes cannot be generated for a transcript."""


def generate_minutes(
    transcript: str, title: str = "", meeting_id: int | None = None
) -> MeetingMinutes:
    """Call Gemini for structured minutes. Raises NoteTakerError on failure."""
    if not transcript.strip():
        raise NoteTakerError("cannot generate minutes for an empty transcript")

    prompt = f"Meeting title: {title}\n\nTranscript:\n{transcript}" if title else transcript

    log_event(
        logger,
        "note_taker.requested",
        meeting_id=meeting_id,
        model=settings.model_extraction,
        transcript_chars=len(transcript),
        transcript_lines=transcript.count("\n") + 1,
    )

    started = time.perf_counter()
    try:
        response = get_client().models.generate_content(
            model=settings.model_extraction,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=MeetingMinutes,
                # The SDK assumes a schema implies function calling and warns.
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                ),
            ),
        )
    except Exception as exc:
        log_event(
            logger,
            "note_taker.failed",
            level=logging.ERROR,
            meeting_id=meeting_id,
            model=settings.model_extraction,
            elapsed_ms=round((time.perf_counter() - started) * 1000),
            error=str(exc),
        )
        raise NoteTakerError(f"Gemini call failed: {exc}") from exc

    elapsed_ms = round((time.perf_counter() - started) * 1000)
    usage = getattr(response, "usage_metadata", None)

    minutes = response.parsed
    if not isinstance(minutes, MeetingMinutes):
        log_event(
            logger,
            "note_taker.unparsable",
            level=logging.ERROR,
            meeting_id=meeting_id,
            elapsed_ms=elapsed_ms,
            raw_text=(response.text or "")[:2000],
        )
        raise NoteTakerError("Gemini returned no usable minutes")

    # The full model output, so it can be read back from Cloud Logging and
    # compared against what landed in meeting.minutes_json.
    log_event(
        logger,
        "note_taker.completed",
        meeting_id=meeting_id,
        model=settings.model_extraction,
        elapsed_ms=elapsed_ms,
        prompt_tokens=getattr(usage, "prompt_token_count", None),
        response_tokens=getattr(usage, "candidates_token_count", None),
        total_tokens=getattr(usage, "total_token_count", None),
        key_point_count=len(minutes.key_points),
        action_item_count=len(minutes.action_items),
        minutes=minutes.model_dump(),
    )
    return minutes


def take_notes(meeting_id: int) -> Meeting:
    """Generate and persist minutes for an already-stored meeting.

    Safe to call again on a meeting whose extraction failed, which is the
    point of keeping the transcript and the status separate.
    """
    meeting = db.get_meeting(meeting_id)
    if meeting is None:
        raise NoteTakerError(f"no meeting with id {meeting_id}")

    db.set_meeting_status(meeting_id, MeetingStatus.PROCESSING)
    try:
        minutes = generate_minutes(meeting.transcript, meeting.title, meeting_id)
    except NoteTakerError:
        db.set_meeting_status(meeting_id, MeetingStatus.FAILED)
        raise

    meeting.minutes = minutes
    meeting.status = MeetingStatus.PROCESSED
    db.update_meeting(meeting)

    log_event(
        logger,
        "note_taker.stored",
        meeting_id=meeting_id,
        status=meeting.status.value,
        minutes_chars=len(minutes.model_dump_json()),
    )

    # Event: minutes ready → background idea extraction (does not block the caller).
    from agents.idea_jobs import on_minutes_ready

    on_minutes_ready(meeting_id)
    refreshed = db.get_meeting(meeting_id)
    return refreshed if refreshed is not None else meeting


def transcript_fingerprint(text: str) -> str:
    """Stable id for a transcript body so duplicate uploads reuse one meeting."""
    normalized = "\n".join(
        line.strip() for line in text.replace("\r\n", "\n").split("\n") if line.strip()
    )
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"transcript:{digest}"


def ingest(
    raw: str,
    title: str,
    filename: str | None = None,
    source: MeetingSource = MeetingSource.UPLOAD,
    occurred_at: datetime | None = None,
) -> tuple[Meeting, ParsedTranscript, bool]:
    """Parse a transcript and store it. Does not call the model.

    Returns ``(meeting, parsed, created)``. When the same transcript body was
    uploaded before, returns the existing meeting with ``created=False``.

    Parsing happens before the insert so a malformed file is rejected with a
    400 instead of leaving an unusable row behind.
    """
    parsed = parse_transcript(raw, filename)
    fingerprint = transcript_fingerprint(parsed.text)
    existing = db.find_meeting_by_external_id(fingerprint)
    if existing is None:
        existing = db.find_meeting_by_transcript(parsed.text)
    if existing is not None:
        log_event(
            logger,
            "note_taker.ingest_duplicate",
            meeting_id=existing.id,
            external_id=fingerprint,
        )
        return existing, parsed, False

    meeting = db.create_meeting(
        Meeting(
            title=title.strip(),
            transcript=parsed.text,
            occurred_at=occurred_at,
            external_source=source,
            external_id=fingerprint,
            status=MeetingStatus.PENDING,
        )
    )
    return meeting, parsed, True
