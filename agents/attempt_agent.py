"""Plan and draft repository changes for an approved idea."""

from __future__ import annotations

from pydantic import BaseModel, Field
from google.genai import types

from llm import get_client
from schemas import ArchitectureCatalog, Idea, Meeting, TechnicalPlan


class FileChange(BaseModel):
    path: str = Field(description="Repository-relative path to create or update")
    content: str = Field(description="Complete UTF-8 file content after the change")
    rationale: str = ""


class FileChangeBatch(BaseModel):
    changes: list[FileChange] = Field(default_factory=list)


def generate_plan(
    idea: Idea,
    meeting: Meeting,
    catalog: ArchitectureCatalog,
    model: str,
) -> TechnicalPlan:
    """Create a repo-grounded plan from the idea and its meeting evidence."""
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
            system_instruction=(
                "You are a careful senior engineer preparing a small, testable attempt "
                "in the provided repository. Ground every change in the catalog and "
                "meeting evidence. Prefer a narrow implementation. List blockers and "
                "external requirements explicitly; never claim external systems are "
                "available when they are not. Return a structured technical plan."
            ),
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


def generate_changes(
    idea: Idea,
    plan: TechnicalPlan,
    catalog: ArchitectureCatalog,
    source_context: str,
    model: str,
) -> FileChangeBatch:
    """Generate a proposed patch as complete file contents (not executed here)."""
    response = get_client().models.generate_content(
        model=model,
        contents=(
            f"Approved idea: {idea.title}\n{idea.description}\n"
            f"Meeting quote: {idea.quote}\n"
            f"Repository catalog:\n{catalog.to_markdown()}\n\n"
            f"Technical plan:\n{plan.model_dump_json(indent=2)}\n\n"
            f"Relevant repository files:\n{source_context}"
        ),
        config=types.GenerateContentConfig(
            system_instruction=(
                "Implement the approved plan as a minimal, reviewable code change. "
                "Return only files that need to be created or changed, with complete "
                "UTF-8 contents. Use repository conventions from the supplied files. "
                "Do not include secrets, credentials, generated artifacts, or files "
                "outside the repository. If the plan is blocked or there is not enough "
                "context to make a safe change, return an empty changes list."
            ),
            response_mime_type="application/json",
            response_schema=FileChangeBatch,
            temperature=0.1,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )
    if isinstance(response.parsed, FileChangeBatch):
        return response.parsed
    if response.text:
        return FileChangeBatch.model_validate_json(response.text)
    raise RuntimeError("The coding model returned no usable changes.")
