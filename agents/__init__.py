"""Gemini-backed agents: meeting notes, ideas, and repository onboarding."""

from agents.idea_extractor import (
    IdeaExtractorError,
    extract_ideas,
    generate_ideas,
    normalize_idea_key,
)
from agents.idea_jobs import on_minutes_ready
from agents.meeting_jobs import queue_minutes
from agents.note_taker import NoteTakerError, generate_minutes, ingest, take_notes
from agents.repo_onboarder import (
    RepoOnboarder,
    generate_architecture_catalog,
    onboard_repository,
)
from agents.transcript import TranscriptError, parse_transcript

__all__ = [
    "IdeaExtractorError",
    "extract_ideas",
    "generate_ideas",
    "normalize_idea_key",
    "on_minutes_ready",
    "queue_minutes",
    "NoteTakerError",
    "TranscriptError",
    "generate_minutes",
    "ingest",
    "take_notes",
    "parse_transcript",
    "RepoOnboarder",
    "onboard_repository",
    "generate_architecture_catalog",
]
