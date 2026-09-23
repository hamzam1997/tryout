"""Domain models and schemas for tryout."""

from enum import Enum
from pydantic import BaseModel, Field


class RepoSource(str, Enum):
    GITHUB = "github"
    LOCAL = "local"
    DEMO = "demo"


class MeetingSource(str, Enum):
    MEET = "meet"
    UPLOAD = "upload"
    PASTE = "paste"
    SEED = "seed"


class IdeaStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AttemptStatus(str, Enum):
    QUEUED = "QUEUED"
    PLANNING = "PLANNING"
    CODING = "CODING"
    TESTING = "TESTING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class FrictionCategory(str, Enum):
    EXTERNAL_SERVICE_DEPENDENCY = "EXTERNAL_SERVICE_DEPENDENCY"
    AUTH_CREDENTIAL_REQUIRED = "AUTH_CREDENTIAL_REQUIRED"
    SCHEMA_MIGRATION_REQUIRED = "SCHEMA_MIGRATION_REQUIRED"
    CROSS_TEAM_CONTRACT = "CROSS_TEAM_CONTRACT"
    PRODUCT_DECISION = "PRODUCT_DECISION"


class ModelEntry(BaseModel):
    name: str
    fields: list[str] = Field(default_factory=list)


class RouteEntry(BaseModel):
    method: str = ""
    path: str
    handler: str = ""


class IntegrationEntry(BaseModel):
    name: str
    auth: str = ""
    env_keys: list[str] = Field(default_factory=list)


class ArchitectureCatalog(BaseModel):
    name: str = ""
    language: str = ""
    framework: str = ""
    summary: str = ""
    internal_models: list[ModelEntry] = Field(default_factory=list)
    api_routes: list[RouteEntry] = Field(default_factory=list)
    external_integrations: list[IntegrationEntry] = Field(default_factory=list)
    config_schema: list[str] = Field(default_factory=list)
    codeowners: dict[str, str] = Field(default_factory=dict)


class MeetingMinutes(BaseModel):
    summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)


class PlanStep(BaseModel):
    order: int
    action: str
    target: str = ""
    rationale: str = ""


class TechnicalPlan(BaseModel):
    summary: str = ""
    repo_changes: list[PlanStep] = Field(default_factory=list)
    external_requirements: list[str] = Field(default_factory=list)
    mock_strategy: str = ""


class ReadinessItem(BaseModel):
    task: str
    owner: str = ""
    done: bool = False


class Repository(BaseModel):
    id: int | None = None
    name: str
    source: str
    source_type: RepoSource = RepoSource.LOCAL
    source_ref: str | None = None
    catalog: ArchitectureCatalog | None = None
    catalog_generated_at: str | None = None
    created_at: str | None = None


class Meeting(BaseModel):
    id: int | None = None
    title: str
    occurred_at: str | None = None
    external_source: MeetingSource = MeetingSource.PASTE
    external_id: str | None = None
    external_url: str | None = None
    source_type: str | None = None
    transcript: str
    minutes: MeetingMinutes | None = None
    created_at: str | None = None


class Idea(BaseModel):
    id: int | None = None
    meeting_id: int
    title: str
    description: str = ""
    source_quote: str = ""
    speaker: str = ""
    timestamp: str = ""
    urgency: str = ""
    feasibility_hypothesis: str = ""
    fingerprint: str = ""
    duplicate_of_id: int | None = None
    status: IdeaStatus = IdeaStatus.PENDING
    created_at: str | None = None


class Attempt(BaseModel):
    id: int | None = None
    idea_id: int
    repository_id: int
    repo_ref: str | None = None
    status: AttemptStatus = AttemptStatus.QUEUED
    plan: TechnicalPlan | None = None
    diff: str | None = None
    test_exit_code: int | None = None
    test_stdout: str | None = None
    test_stderr: str | None = None
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    created_at: str | None = None


class FrictionLog(BaseModel):
    id: int | None = None
    attempt_id: int
    category: FrictionCategory
    service_name: str = ""
    owning_team: str = ""
    mock_implementation_path: str = ""
    required_action: str = ""
    readiness_checklist: list[ReadinessItem] = Field(default_factory=list)
    created_at: str | None = None
