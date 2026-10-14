"""Technical planner: turn an approved idea into a repo-grounded plan before coding."""

from __future__ import annotations

from google.genai import types

from llm import get_client
from schemas import ArchitectureCatalog, Idea, Meeting, TechnicalPlan

_SYSTEM = (
    "You are a careful senior engineer planning a small, testable prototype of an approved "
    "idea in the given repository. Ground every step in the architecture catalog and the "
    "meeting evidence, and keep the change narrow.\n"
    "Separate the two kinds of work strictly:\n"
    "- repo_changes: files inside this repository to create or modify, in order.\n"
    "- external_requirements: every service, third-party API, credential or other team's "
    "system the idea needs that this repository does not own. Never assume they are "
    "available.\n"
    "- mock_strategy: how each external requirement is mocked so the prototype and its "
    "tests run locally without credentials or network."
)


def generate_plan(idea: Idea, meeting: Meeting, catalog: ArchitectureCatalog, model: str) -> TechnicalPlan:
    response = get_client().models.generate_content(
        model=model,
        contents=(
            f"Repository architecture catalog:\n{catalog.to_markdown()}\n\n"
            f"Meeting: {meeting.title}\nTranscript:\n{meeting.transcript}\n\n"
            f"Approved idea: {idea.title}\n{idea.description}\n"
            f"Evidence quote: {idea.quote}\n"
            f"Attempt hypothesis: {idea.attempt_hypothesis}\n"
            f"Catalog touchpoints: {', '.join(idea.catalog_refs)}"
        ),
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM,
            response_mime_type="application/json",
            response_schema=TechnicalPlan,
            temperature=0.2,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )
    if isinstance(response.parsed, TechnicalPlan):
        return response.parsed
    if response.text:
        return TechnicalPlan.model_validate_json(response.text)
    raise RuntimeError("The planning model returned no usable plan.")


def plan_markdown(plan: TechnicalPlan) -> str:
    """The plan as prompt text for the coding agent."""
    steps = "\n".join(f"{s.order}. {s.action} `{s.target}`: {s.rationale}" for s in plan.repo_changes)
    external = "\n".join(f"- {r}" for r in plan.external_requirements) or "- none"
    return (
        f"Plan summary: {plan.summary}\n\nIn-repo changes:\n{steps}\n\n"
        f"External requirements (mock each one):\n{external}\n\nMock strategy: {plan.mock_strategy}"
    )
