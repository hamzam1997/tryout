"""Gemini-backed agents: meeting notes and repository onboarding."""

from agents.note_taker import NoteTakerError, generate_minutes, ingest, take_notes
from agents.repo_onboarder import (
    RepoOnboarder,
    generate_architecture_catalog,
    onboard_repository,
)
from agents.transcript import TranscriptError, parse_transcript

__all__ = [
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
