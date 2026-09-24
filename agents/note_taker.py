"""Note taker agent: transcript in, meeting minutes out.

Ingestion writes the meeting row before calling Gemini, so a model failure
costs a retry rather than the upload. Meeting.status records which of those
happened.
"""

from __future__ import annotations

import logging
from datetime import datetime

from google.genai import types

import database as db
from agents.transcript import ParsedTranscript, parse_transcript
from config import settings
from llm import get_client
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


def generate_minutes(transcript: str, title: str = "") -> MeetingMinutes:
    """Call Gemini for structured minutes. Raises NoteTakerError on failure."""
    if not transcript.strip():
        raise NoteTakerError("cannot generate minutes for an empty transcript")

    prompt = f"Meeting title: {title}\n\nTranscript:\n{transcript}" if title else transcript

    try:
        response = get_client().models.generate_content(
            model=settings.model_extraction,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=MeetingMinutes,
                temperature=0.2,
                # The SDK assumes a schema implies function calling and warns.
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                ),
            ),
        )
    except Exception as exc:
        raise NoteTakerError(f"Gemini call failed: {exc}") from exc

    minutes = response.parsed
    if not isinstance(minutes, MeetingMinutes):
        raise NoteTakerError("Gemini returned no usable minutes")
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
        minutes = generate_minutes(meeting.transcript, meeting.title)
    except NoteTakerError:
        db.set_meeting_status(meeting_id, MeetingStatus.FAILED)
        logger.exception("note taker failed for meeting %s", meeting_id)
        raise

    meeting.minutes = minutes
    meeting.status = MeetingStatus.PROCESSED
    db.update_meeting(meeting)
    return meeting


def ingest(
    raw: str,
    title: str,
    filename: str | None = None,
    source: MeetingSource = MeetingSource.UPLOAD,
    occurred_at: datetime | None = None,
) -> tuple[Meeting, ParsedTranscript]:
    """Parse a transcript and store it. Does not call the model.

    Parsing happens before the insert so a malformed file is rejected with a
    400 instead of leaving an unusable row behind.
    """
    parsed = parse_transcript(raw, filename)
    meeting = db.create_meeting(
        Meeting(
            title=title.strip(),
            transcript=parsed.text,
            occurred_at=occurred_at,
            external_source=source,
            status=MeetingStatus.PENDING,
        )
    )
    return meeting, parsed
