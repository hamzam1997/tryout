"""Background minutes generation after transcript ingest.

Mirrors repository onboarding: the HTTP handler persists the meeting, marks
it PROCESSING, and returns immediately; Gemini minutes run in a daemon thread.
When minutes land, `take_notes` fires `on_minutes_ready` for idea extraction.
"""

from __future__ import annotations

import logging
import threading

import database as db
from agents.note_taker import NoteTakerError, take_notes
from logging_setup import log_event
from schemas import MeetingStatus

logger = logging.getLogger(__name__)

# When True, queue_minutes runs inline (used by unit tests).
_FORCE_SYNC = False


def set_force_sync(enabled: bool) -> None:
    """Toggle synchronous minutes generation for tests."""
    global _FORCE_SYNC
    _FORCE_SYNC = enabled


def execute_minutes(meeting_id: int) -> None:
    """Run note-taking; failures land as MeetingStatus.FAILED."""
    log_event(logger, "meeting_jobs.started", meeting_id=meeting_id)
    try:
        take_notes(meeting_id)
    except NoteTakerError as exc:
        # take_notes already persists FAILED.
        log_event(
            logger,
            "meeting_jobs.failed",
            level=logging.ERROR,
            meeting_id=meeting_id,
            error=str(exc),
        )
        return
    except Exception as exc:
        db.set_meeting_status(meeting_id, MeetingStatus.FAILED)
        log_event(
            logger,
            "meeting_jobs.failed",
            level=logging.ERROR,
            meeting_id=meeting_id,
            error=str(exc),
        )
        return

    log_event(logger, "meeting_jobs.completed", meeting_id=meeting_id)


def queue_minutes(meeting_id: int) -> None:
    """Mark the meeting PROCESSING and start background minutes generation."""
    meeting = db.get_meeting(meeting_id)
    if meeting is None:
        log_event(
            logger,
            "meeting_jobs.skipped_missing_meeting",
            level=logging.WARNING,
            meeting_id=meeting_id,
        )
        return

    db.set_meeting_status(meeting_id, MeetingStatus.PROCESSING)
    log_event(logger, "meeting_jobs.queued", meeting_id=meeting_id)

    if _FORCE_SYNC:
        execute_minutes(meeting_id)
        return

    worker = threading.Thread(
        target=execute_minutes,
        args=(meeting_id,),
        name=f"meeting-minutes-{meeting_id}",
        daemon=True,
    )
    worker.start()
