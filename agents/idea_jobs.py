"""Background idea extraction triggered when meeting minutes are ready.

This is the event bridge between note-taking and idea extraction: callers
invoke `on_minutes_ready(meeting_id)` after minutes are stored; extraction
runs in a daemon thread so the HTTP request can return immediately.
"""

from __future__ import annotations

import logging
import threading

import database as db
from agents.idea_extractor import IdeaExtractorError, extract_ideas
from logging_setup import log_event
from schemas import IdeasExtractStatus

logger = logging.getLogger(__name__)

# When True, on_minutes_ready runs inline (used by unit tests).
_FORCE_SYNC = False


def set_force_sync(enabled: bool) -> None:
    """Toggle synchronous extraction for tests."""
    global _FORCE_SYNC
    _FORCE_SYNC = enabled


def execute_idea_extraction(meeting_id: int) -> None:
    """Run idea extraction and persist PROCESSING → PROCESSED/FAILED."""
    log_event(logger, "idea_jobs.started", meeting_id=meeting_id)
    try:
        extract_ideas(meeting_id)
    except IdeaExtractorError as exc:
        db.set_meeting_ideas_state(
            meeting_id,
            IdeasExtractStatus.FAILED,
            ideas_error=str(exc),
        )
        log_event(
            logger,
            "idea_jobs.failed",
            level=logging.ERROR,
            meeting_id=meeting_id,
            error=str(exc),
        )
        return
    except Exception as exc:
        db.set_meeting_ideas_state(
            meeting_id,
            IdeasExtractStatus.FAILED,
            ideas_error=str(exc),
        )
        log_event(
            logger,
            "idea_jobs.failed",
            level=logging.ERROR,
            meeting_id=meeting_id,
            error=str(exc),
        )
        return

    db.set_meeting_ideas_state(
        meeting_id,
        IdeasExtractStatus.PROCESSED,
        ideas_error=None,
    )
    log_event(logger, "idea_jobs.completed", meeting_id=meeting_id)


def on_minutes_ready(meeting_id: int) -> None:
    """Event handler: minutes just landed — start background idea extraction."""
    meeting = db.get_meeting(meeting_id)
    if meeting is None:
        log_event(
            logger,
            "idea_jobs.skipped_missing_meeting",
            level=logging.WARNING,
            meeting_id=meeting_id,
        )
        return

    db.set_meeting_ideas_state(
        meeting_id,
        IdeasExtractStatus.PROCESSING,
        ideas_error=None,
    )
    log_event(logger, "idea_jobs.queued", meeting_id=meeting_id)

    if _FORCE_SYNC:
        execute_idea_extraction(meeting_id)
        return

    worker = threading.Thread(
        target=execute_idea_extraction,
        args=(meeting_id,),
        name=f"idea-extract-{meeting_id}",
        daemon=True,
    )
    worker.start()
