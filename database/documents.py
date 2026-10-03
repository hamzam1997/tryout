"""Pydantic document models strictly for Google Cloud Firestore storage.

These models represent the exact schema stored in Firestore collections,
isolated from domain/API DTOs in `schemas.py`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, ClassVar
from pydantic import BaseModel, Field

import schemas


def utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc)


class RepositoryDoc(BaseModel):
    """Document stored in Firestore `/repositories/{id}`."""

    COLLECTION: ClassVar[str] = "repositories"

    id: int
    name: str
    source: str
    source_type: str = "local"
    source_ref: str | None = None
    catalog: dict[str, Any] | None = None
    catalog_status: str = "ready"
    catalog_error: str | None = None
    catalog_generated_at: str | None = None
    created_at: str = Field(default_factory=lambda: utc_now().isoformat())

    def to_doc(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_doc(cls, data: dict[str, Any]) -> RepositoryDoc:
        return cls.model_validate(data)

    def to_domain(self) -> schemas.Repository:
        catalog_obj = None
        if self.catalog:
            catalog_obj = schemas.ArchitectureCatalog.model_validate(self.catalog)
        gen_at = None
        if self.catalog_generated_at:
            gen_at = datetime.fromisoformat(self.catalog_generated_at)
        created = None
        if self.created_at:
            created = datetime.fromisoformat(self.created_at)

        return schemas.Repository(
            id=self.id,
            name=self.name,
            source=self.source,
            source_type=schemas.RepoSource(self.source_type),
            source_ref=self.source_ref,
            catalog=catalog_obj,
            catalog_status=self.catalog_status,
            catalog_error=self.catalog_error,
            catalog_generated_at=gen_at,
            created_at=created,
        )

    @classmethod
    def from_domain(cls, repo: schemas.Repository) -> RepositoryDoc:
        catalog_dict = repo.catalog.model_dump(mode="json") if repo.catalog else None
        gen_at = (
            repo.catalog_generated_at.isoformat()
            if repo.catalog_generated_at
            else None
        )
        created = repo.created_at.isoformat() if repo.created_at else utc_now().isoformat()
        return cls(
            id=repo.id or 0,
            name=repo.name,
            source=repo.source,
            source_type=repo.source_type.value,
            source_ref=repo.source_ref,
            catalog=catalog_dict,
            catalog_status=repo.catalog_status,
            catalog_error=repo.catalog_error,
            catalog_generated_at=gen_at,
            created_at=created,
        )


class MeetingDoc(BaseModel):
    """Document stored in Firestore `/meetings/{id}`."""

    COLLECTION: ClassVar[str] = "meetings"

    id: int
    title: str
    occurred_at: str | None = None
    external_source: str = "paste"
    external_id: str | None = None
    external_url: str | None = None
    transcript: str
    minutes: dict[str, Any] | None = None
    status: str = "PENDING"
    ideas_status: str = "PENDING"
    ideas_error: str | None = None
    created_at: str = Field(default_factory=lambda: utc_now().isoformat())

    def to_doc(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_doc(cls, data: dict[str, Any]) -> MeetingDoc:
        return cls.model_validate(data)

    def to_domain(self) -> schemas.Meeting:
        minutes_obj = None
        if self.minutes:
            minutes_obj = schemas.MeetingMinutes.model_validate(self.minutes)
        occ = None
        if self.occurred_at:
            occ = datetime.fromisoformat(self.occurred_at)
        created = None
        if self.created_at:
            created = datetime.fromisoformat(self.created_at)

        return schemas.Meeting(
            id=self.id,
            title=self.title,
            occurred_at=occ,
            external_source=schemas.MeetingSource(self.external_source),
            external_id=self.external_id,
            external_url=self.external_url,
            transcript=self.transcript,
            minutes=minutes_obj,
            status=schemas.MeetingStatus(self.status),
            ideas_status=schemas.IdeasExtractStatus(self.ideas_status),
            ideas_error=self.ideas_error,
            created_at=created,
        )

    @classmethod
    def from_domain(cls, meeting: schemas.Meeting) -> MeetingDoc:
        occ = meeting.occurred_at.isoformat() if meeting.occurred_at else None
        created = (
            meeting.created_at.isoformat()
            if meeting.created_at
            else utc_now().isoformat()
        )
        minutes_dict = meeting.minutes.model_dump(mode="json") if meeting.minutes else None
        return cls(
            id=meeting.id or 0,
            title=meeting.title,
            occurred_at=occ,
            external_source=meeting.external_source.value,
            external_id=meeting.external_id,
            external_url=meeting.external_url,
            transcript=meeting.transcript,
            minutes=minutes_dict,
            status=meeting.status.value,
            ideas_status=meeting.ideas_status.value,
            ideas_error=meeting.ideas_error,
            created_at=created,
        )


class IdeaDoc(BaseModel):
    """Document stored in Firestore `/ideas/{id}`."""

    COLLECTION: ClassVar[str] = "ideas"

    id: int
    meeting_id: int
    repository_id: int | None = None
    title: str
    description: str = ""
    quote: str = ""
    speaker: str = ""
    cue_time: str = ""
    priority: str = ""
    attempt_hypothesis: str = ""
    catalog_refs: list[str] = Field(default_factory=list)
    idea_key: str = ""
    original_idea_id: int | None = None
    status: str = "PENDING"
    approved_by: str | None = None
    approved_at: str | None = None
    created_at: str = Field(default_factory=lambda: utc_now().isoformat())

    def to_doc(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_doc(cls, data: dict[str, Any]) -> IdeaDoc:
        return cls.model_validate(data)

    def to_domain(self) -> schemas.Idea:
        app_at = None
        if self.approved_at:
            app_at = datetime.fromisoformat(self.approved_at)
        created = None
        if self.created_at:
            created = datetime.fromisoformat(self.created_at)

        return schemas.Idea(
            id=self.id,
            meeting_id=self.meeting_id,
            repository_id=self.repository_id,
            title=self.title,
            description=self.description,
            quote=self.quote,
            speaker=self.speaker,
            cue_time=self.cue_time,
            priority=self.priority,
            attempt_hypothesis=self.attempt_hypothesis,
            catalog_refs=list(self.catalog_refs or []),
            idea_key=self.idea_key,
            original_idea_id=self.original_idea_id,
            status=schemas.IdeaStatus(self.status),
            approved_by=self.approved_by,
            approved_at=app_at,
            created_at=created,
        )

    @classmethod
    def from_domain(cls, idea: schemas.Idea) -> IdeaDoc:
        app_at = idea.approved_at.isoformat() if idea.approved_at else None
        created = idea.created_at.isoformat() if idea.created_at else utc_now().isoformat()
        return cls(
            id=idea.id or 0,
            meeting_id=idea.meeting_id,
            repository_id=idea.repository_id,
            title=idea.title,
            description=idea.description,
            quote=idea.quote,
            speaker=idea.speaker,
            cue_time=idea.cue_time,
            priority=idea.priority,
            attempt_hypothesis=idea.attempt_hypothesis,
            catalog_refs=list(idea.catalog_refs or []),
            idea_key=idea.idea_key,
            original_idea_id=idea.original_idea_id,
            status=idea.status.value,
            approved_by=idea.approved_by,
            approved_at=app_at,
            created_at=created,
        )


class AttemptDoc(BaseModel):
    """Document stored in Firestore `/attempts/{id}`."""

    COLLECTION: ClassVar[str] = "attempts"

    id: int
    idea_id: int
    repository_id: int
    repo_ref: str | None = None
    base_branch: str | None = None
    branch_name: str | None = None
    pull_request_url: str | None = None
    status: str = "QUEUED"
    plan: dict[str, Any] | None = None
    diff: str | None = None
    test_exit_code: int | None = None
    test_stdout: str | None = None
    test_stderr: str | None = None
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    created_at: str = Field(default_factory=lambda: utc_now().isoformat())

    def to_doc(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_doc(cls, data: dict[str, Any]) -> AttemptDoc:
        return cls.model_validate(data)

    def to_domain(self) -> schemas.Attempt:
        plan_obj = None
        if self.plan:
            plan_obj = schemas.TechnicalPlan.model_validate(self.plan)
        s_at = datetime.fromisoformat(self.started_at) if self.started_at else None
        f_at = datetime.fromisoformat(self.finished_at) if self.finished_at else None
        created = datetime.fromisoformat(self.created_at) if self.created_at else None

        return schemas.Attempt(
            id=self.id,
            idea_id=self.idea_id,
            repository_id=self.repository_id,
            repo_ref=self.repo_ref,
            base_branch=self.base_branch,
            branch_name=self.branch_name,
            pull_request_url=self.pull_request_url,
            status=schemas.AttemptStatus(self.status),
            plan=plan_obj,
            diff=self.diff,
            test_exit_code=self.test_exit_code,
            test_stdout=self.test_stdout,
            test_stderr=self.test_stderr,
            error=self.error,
            started_at=s_at,
            finished_at=f_at,
            created_at=created,
        )

    @classmethod
    def from_domain(cls, attempt: schemas.Attempt) -> AttemptDoc:
        plan_dict = attempt.plan.model_dump(mode="json") if attempt.plan else None
        s_at = attempt.started_at.isoformat() if attempt.started_at else None
        f_at = attempt.finished_at.isoformat() if attempt.finished_at else None
        created = (
            attempt.created_at.isoformat()
            if attempt.created_at
            else utc_now().isoformat()
        )
        return cls(
            id=attempt.id or 0,
            idea_id=attempt.idea_id,
            repository_id=attempt.repository_id,
            repo_ref=attempt.repo_ref,
            base_branch=attempt.base_branch,
            branch_name=attempt.branch_name,
            pull_request_url=attempt.pull_request_url,
            status=attempt.status.value,
            plan=plan_dict,
            diff=attempt.diff,
            test_exit_code=attempt.test_exit_code,
            test_stdout=attempt.test_stdout,
            test_stderr=attempt.test_stderr,
            error=attempt.error,
            started_at=s_at,
            finished_at=f_at,
            created_at=created,
        )


class FrictionLogDoc(BaseModel):
    """Document stored in Firestore `/friction_logs/{id}`."""

    COLLECTION: ClassVar[str] = "friction_logs"

    id: int
    attempt_id: int
    category: str
    service_name: str = ""
    owning_team: str = ""
    mock_implementation_path: str = ""
    required_action: str = ""
    readiness_checklist: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: utc_now().isoformat())

    def to_doc(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_doc(cls, data: dict[str, Any]) -> FrictionLogDoc:
        return cls.model_validate(data)

    def to_domain(self) -> schemas.FrictionLog:
        checklist = [
            schemas.ReadinessItem.model_validate(item)
            for item in self.readiness_checklist
        ]
        created = datetime.fromisoformat(self.created_at) if self.created_at else None
        return schemas.FrictionLog(
            id=self.id,
            attempt_id=self.attempt_id,
            category=schemas.FrictionCategory(self.category),
            service_name=self.service_name,
            owning_team=self.owning_team,
            mock_implementation_path=self.mock_implementation_path,
            required_action=self.required_action,
            readiness_checklist=checklist,
            created_at=created,
        )

    @classmethod
    def from_domain(cls, log: schemas.FrictionLog) -> FrictionLogDoc:
        checklist_dicts = [
            item.model_dump(mode="json") for item in log.readiness_checklist
        ]
        created = log.created_at.isoformat() if log.created_at else utc_now().isoformat()
        return cls(
            id=log.id or 0,
            attempt_id=log.attempt_id,
            category=log.category.value,
            service_name=log.service_name,
            owning_team=log.owning_team,
            mock_implementation_path=log.mock_implementation_path,
            required_action=log.required_action,
            readiness_checklist=checklist_dicts,
            created_at=created,
        )


class UserDoc(BaseModel):
    """Document stored in Firestore `/users/{uid}`."""

    COLLECTION: ClassVar[str] = "users"

    uid: str
    email: str | None = None
    name: str | None = None
    avatar_url: str | None = None
    provider: str | None = None
    github_login: str | None = None
    created_at: str = Field(default_factory=lambda: utc_now().isoformat())
    last_login_at: str = Field(default_factory=lambda: utc_now().isoformat())

    def to_doc(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_doc(cls, data: dict[str, Any]) -> UserDoc:
        return cls.model_validate(data)

    def to_domain(self) -> schemas.User:
        created = datetime.fromisoformat(self.created_at) if self.created_at else None
        last_login = datetime.fromisoformat(self.last_login_at) if self.last_login_at else None
        return schemas.User(
            uid=self.uid,
            email=self.email,
            name=self.name,
            avatar_url=self.avatar_url,
            provider=self.provider,
            github_login=self.github_login,
            created_at=created,
            last_login_at=last_login,
        )

    @classmethod
    def from_domain(cls, user: schemas.User) -> UserDoc:
        created = user.created_at.isoformat() if user.created_at else utc_now().isoformat()
        last_login = user.last_login_at.isoformat() if user.last_login_at else utc_now().isoformat()
        return cls(
            uid=user.uid,
            email=user.email,
            name=user.name,
            avatar_url=user.avatar_url,
            provider=user.provider,
            github_login=user.github_login,
            created_at=created,
            last_login_at=last_login,
        )
