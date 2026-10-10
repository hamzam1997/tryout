"""Turn a finished harness attempt into structured friction logs.

Every mock, credential, migration or cross-team dependency the prototype had to
work around is a blocker a human must clear before the idea can ship. These are
persisted to `friction_logs` for the org-wide bottleneck map.
"""

from __future__ import annotations

import logging

from google.genai import types
from pydantic import BaseModel, Field

import database as db
from llm import get_client
from schemas import (
    ArchitectureCatalog,
    Attempt,
    FrictionCategory,
    FrictionLog,
    Idea,
    ReadinessItem,
)

logger = logging.getLogger(__name__)

# ~100k tokens: far below the model's context, so real attempt diffs fit whole.
_MAX_DIFF_CHARS = 400_000

_SYSTEM = (
    "You analyse a finished prototype attempt and list every blocker that stops the idea "
    "from shipping to production. Each mock adapter, credential, schema change or other "
    "team's service in the diff is evidence. Rules:\n"
    "- One entry per distinct blocker; do not pad. Return an empty list if there are none.\n"
    "- category must be one of: EXTERNAL_SERVICE_DEPENDENCY (a service we do not own or "
    "cannot reach), AUTH_CREDENTIAL_REQUIRED (API keys, IAM roles, env vars), "
    "SCHEMA_MIGRATION_REQUIRED (new/changed stored data), CROSS_TEAM_CONTRACT (another "
    "team must build or approve something), PRODUCT_DECISION (a rule nobody has defined).\n"
    "- owning_team: use owners from the catalog/CODEOWNERS (e.g. @team-comms). If the "
    "owner is not evidenced, write 'unknown'; never invent a team.\n"
    "- mock_implementation_path: the repo path of the mock that stands in for it, or ''.\n"
    "- required_action: one sentence a human can act on.\n"
    "- readiness_checklist: 1-4 concrete tasks, each with the owner who must do it, "
    "naming env vars / IAM roles where relevant."
)


class FrictionItem(BaseModel):
    category: FrictionCategory
    service_name: str = Field(description="Service or system involved, e.g. 'notifications-service'")
    owning_team: str = "unknown"
    mock_implementation_path: str = ""
    required_action: str
    readiness_checklist: list[ReadinessItem] = Field(default_factory=list)


class FrictionBatch(BaseModel):
    items: list[FrictionItem] = Field(default_factory=list)


def _diff_for_prompt(diff: str) -> str:
    """Changed-file list first, so every file is known even if the diff is cut."""
    files = [l.split(" b/", 1)[-1] for l in diff.splitlines() if l.startswith("diff --git")]
    text = diff[:_MAX_DIFF_CHARS]
    if len(diff) > _MAX_DIFF_CHARS:
        text += f"\n[truncated, {len(diff) - _MAX_DIFF_CHARS} more chars]"
    return "Changed files:\n" + "\n".join(f"- {f}" for f in files) + f"\n\nDiff:\n{text}"


def classify_friction(
    idea: Idea,
    catalog: ArchitectureCatalog,
    diff: str,
    testing_notes: str,
    events: list,
    model: str,
) -> list[FrictionItem]:
    # Cap prompt size: keep only the last 40 steps. The harness runs at most 25 model
    # turns, but a turn can issue several tool calls, so a run can log more than 40
    # events; any older ones are dropped (the diff and notes still cover that work).
    steps = "\n".join(f"- {e.action}: {e.detail}" for e in events[-40:])
    response = get_client().models.generate_content(
        model=model,
        contents=(
            f"Idea: {idea.title}\n{idea.description}\nMeeting quote: {idea.quote}\n\n"
            f"Repository catalog (integrations, owners):\n{catalog.to_markdown()}\n\n"
            f"Agent steps:\n{steps}\n\nTesting notes:\n{testing_notes}\n\n"
            f"{_diff_for_prompt(diff)}"
        ),
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM,
            response_mime_type="application/json",
            response_schema=FrictionBatch,
            temperature=0.1,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )
    if isinstance(response.parsed, FrictionBatch):
        return response.parsed.items
    if response.text:
        return FrictionBatch.model_validate_json(response.text).items
    raise RuntimeError("The friction model returned no usable result.")


def readiness_markdown(logs: list[FrictionLog]) -> str:
    """Production readiness checklist, for the PR body."""
    if not logs:
        return ""
    lines = ["\n\n## Production readiness checklist"]
    for log in logs:
        lines.append(f"\n**{log.service_name}** ({log.category.value}, owner: {log.owning_team})")
        lines.append(f"- {log.required_action}")
        lines += [f"- [ ] {i.task} — {i.owner or 'unassigned'}" for i in log.readiness_checklist]
    return "\n".join(lines)


def record_friction(
    attempt: Attempt,
    idea: Idea,
    catalog: ArchitectureCatalog,
    diff: str,
    testing_notes: str,
    model: str,
) -> list[FrictionLog]:
    """Classify and persist friction for a live harness result. Never raises."""
    try:
        items = classify_friction(idea, catalog, diff, testing_notes, attempt.events or [], model)
        return [
            db.create_friction_log(FrictionLog(attempt_id=attempt.id, **item.model_dump()))
            for item in items
        ]
    except Exception:
        logger.exception("Friction classification failed for attempt %s", attempt.id)
        return []
