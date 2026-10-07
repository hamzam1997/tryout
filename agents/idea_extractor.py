"""Idea extractor agent: catalog-grounded proposals from meeting transcripts."""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path

from google.genai import types

import database as db
from agents.repo_onboarder import RepoOnboarder
from config import settings
from llm import get_client
from logging_setup import log_event
from schemas import (
    ArchitectureCatalog,
    ExtractedIdeaBatch,
    ExtractedIdeaCandidate,
    Idea,
    IdeaStatus,
    RepoSource,
    Repository,
)

logger = logging.getLogger(__name__)

DEFAULT_REPOSITORY_PATH = "https://github.com/hamzam1997/acme-store"


def _default_repositories() -> list[str | Path]:
    """Every onboarded repo with a catalog; the GitHub demo repo if none exist yet."""
    # ponytail: one extraction call per repo; add a meeting→repo picker when repo count grows.
    # GitHub re-cataloguing here runs tokenless, so only public repos work.
    targets: list[str | Path] = []
    for r in db.list_repositories():
        if r.catalog is None:
            continue
        targets.append(r.source if r.source_type == RepoSource.GITHUB else Path(r.source))
    return targets or [DEFAULT_REPOSITORY_PATH]


SYSTEM_INSTRUCTION = """\
You are an idea extractor for engineering and operations meetings.

An idea is a meeting-backed proposal that maps onto the provided ArchitectureCatalog
for the target repository. You are not a free-form action-item scraper.

Rules:
- Precision over recall. Only emit ideas that clearly tie to catalog modules, routes,
  models, integrations, or external_dependencies named in the catalog.
- attemptable ≠ will ship: keep ideas even when they depend on external services
  listed in the catalog (for example notifications-service). Say so in attempt_hypothesis.
- Every idea MUST have a non-empty catalog_refs list naming concrete catalog surfaces
  (module paths, route paths, model names, integration names, or external_dependencies).
- Drop status updates, ticket-volume chatter, audit tasks, PTO/scheduling, and bare
  process decisions with no in-repo code surface.
- Fill attempt_hypothesis from the catalog: what would change in-repo, what is missing,
  and which external teams or services block a full implementation.
- quote must be a verbatim excerpt from the transcript supporting the proposal.
- cue_time is the transcript offset (HH:MM:SS) for that quote, not wall-clock time.
- priority is one of low, medium, or high when inferable; otherwise leave empty.
- idea_key is a stable kebab-case identifier for the underlying proposal across meetings
  (for example auto-notify-delayed-refunds).

Report only what the transcript and catalog support together.\
"""


class IdeaExtractorError(RuntimeError):
    """Raised when ideas cannot be extracted for a meeting."""


def normalize_idea_key(raw: str) -> str:
    """Normalize a model-provided key to stable kebab-case."""
    key = raw.strip().lower()
    key = re.sub(r"[^a-z0-9]+", "-", key)
    return key.strip("-")


def generate_ideas(
    transcript: str,
    catalog: ArchitectureCatalog,
    title: str = "",
    meeting_id: int | None = None,
) -> ExtractedIdeaBatch:
    """Call Gemini for catalog-grounded ideas. Raises IdeaExtractorError on failure."""
    if not transcript.strip():
        raise IdeaExtractorError("cannot extract ideas from an empty transcript")

    catalog_markdown = catalog.to_markdown()
    if not catalog_markdown.strip():
        raise IdeaExtractorError("architecture catalog is empty")

    prompt_parts = [
        "Architecture catalog for the target repository:",
        catalog_markdown,
        "",
    ]
    if title.strip():
        prompt_parts.extend([f"Meeting title: {title.strip()}", ""])
    prompt_parts.extend(["Transcript:", transcript])
    prompt = "\n".join(prompt_parts)

    log_event(
        logger,
        "idea_extractor.requested",
        meeting_id=meeting_id,
        model=settings.model_extraction,
        transcript_chars=len(transcript),
        catalog_chars=len(catalog_markdown),
    )

    started = time.perf_counter()
    try:
        response = get_client().models.generate_content(
            model=settings.model_extraction,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=ExtractedIdeaBatch,
                temperature=0.2,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                ),
            ),
        )
    except Exception as exc:
        log_event(
            logger,
            "idea_extractor.failed",
            level=logging.ERROR,
            meeting_id=meeting_id,
            model=settings.model_extraction,
            elapsed_ms=round((time.perf_counter() - started) * 1000),
            error=str(exc),
        )
        raise IdeaExtractorError(f"Gemini call failed: {exc}") from exc

    elapsed_ms = round((time.perf_counter() - started) * 1000)
    usage = getattr(response, "usage_metadata", None)

    batch = response.parsed
    if not isinstance(batch, ExtractedIdeaBatch):
        log_event(
            logger,
            "idea_extractor.unparsable",
            level=logging.ERROR,
            meeting_id=meeting_id,
            elapsed_ms=elapsed_ms,
            raw_text=(response.text or "")[:2000],
        )
        raise IdeaExtractorError("Gemini returned no usable ideas")

    log_event(
        logger,
        "idea_extractor.completed",
        meeting_id=meeting_id,
        model=settings.model_extraction,
        elapsed_ms=elapsed_ms,
        prompt_tokens=getattr(usage, "prompt_token_count", None),
        response_tokens=getattr(usage, "candidates_token_count", None),
        total_tokens=getattr(usage, "total_token_count", None),
        idea_count=len(batch.ideas),
        ideas=batch.model_dump(),
    )
    return batch


def _candidate_to_idea(
    candidate: ExtractedIdeaCandidate, meeting_id: int, repository_id: int | None = None
) -> Idea:
    idea_key = normalize_idea_key(candidate.idea_key)
    if not idea_key and candidate.title.strip():
        idea_key = normalize_idea_key(candidate.title)

    return Idea(
        meeting_id=meeting_id,
        repository_id=repository_id,
        title=candidate.title.strip() or idea_key or "Untitled idea",
        description=candidate.description.strip(),
        quote=candidate.quote.strip(),
        speaker=candidate.speaker.strip(),
        cue_time=candidate.cue_time.strip(),
        priority=candidate.priority.strip(),
        attempt_hypothesis=candidate.attempt_hypothesis.strip(),
        catalog_refs=list(candidate.catalog_refs),
        idea_key=idea_key,
        status=IdeaStatus.PENDING,
    )


def extract_ideas(
    meeting_id: int,
    repository: Repository | int | str | Path | None = None,
) -> list[Idea]:
    """Extract and persist catalog-grounded ideas for a stored meeting."""
    meeting = db.get_meeting(meeting_id)
    if meeting is None:
        raise IdeaExtractorError(f"no meeting with id {meeting_id}")

    targets = [repository] if repository is not None else _default_repositories()
    stored: list[Idea] = []
    seen_keys: set[str] = set()
    failures: list[str] = []
    for target in targets:
        try:
            stored += _extract_for_repository(meeting, target, seen_keys)
        except IdeaExtractorError as exc:
            failures.append(str(exc))
    if failures and len(failures) == len(targets):
        raise IdeaExtractorError("; ".join(failures))

    log_event(
        logger,
        "idea_extractor.stored",
        meeting_id=meeting_id,
        idea_count=len(stored),
    )
    return stored


def _extract_for_repository(meeting, repo_target, seen_keys: set[str]) -> list[Idea]:
    meeting_id = meeting.id
    onboarder = RepoOnboarder()
    try:
        onboarded = onboarder.onboard(repo_target, return_repo=True)
        if isinstance(onboarded, tuple):
            repository_record, catalog = onboarded
        else:  # Keep injected/custom onboarders that only return the catalog usable.
            repository_record, catalog = None, onboarded
    except Exception as exc:
        log_event(
            logger,
            "idea_extractor.onboard_failed",
            level=logging.ERROR,
            meeting_id=meeting_id,
            repository=str(repo_target),
            error=str(exc),
        )
        raise IdeaExtractorError(f"repository onboarding failed: {exc}") from exc

    if not isinstance(catalog, ArchitectureCatalog):
        raise IdeaExtractorError("repository onboarding did not yield a catalog")

    batch = generate_ideas(
        meeting.transcript,
        catalog,
        title=meeting.title,
        meeting_id=meeting_id,
    )

    stored: list[Idea] = []
    for candidate in batch.ideas:
        if not candidate.catalog_refs:
            log_event(
                logger,
                "idea_extractor.skipped_no_catalog_refs",
                meeting_id=meeting_id,
                title=candidate.title,
            )
            continue

        draft = _candidate_to_idea(
            candidate, meeting_id, repository_record.id if repository_record else None
        )
        if draft.idea_key:
            if draft.idea_key in seen_keys:
                log_event(
                    logger,
                    "idea_extractor.skipped_duplicate_in_batch",
                    meeting_id=meeting_id,
                    idea_key=draft.idea_key,
                )
                continue
            existing = db.find_idea_by_key(draft.idea_key)
            if existing is not None:
                log_event(
                    logger,
                    "idea_extractor.skipped_existing_idea_key",
                    meeting_id=meeting_id,
                    idea_key=draft.idea_key,
                    existing_idea_id=existing.id,
                )
                seen_keys.add(draft.idea_key)
                continue
            seen_keys.add(draft.idea_key)

        idea = db.create_idea(draft)
        stored.append(idea)
    return stored
