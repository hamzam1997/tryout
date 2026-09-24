"""Pydantic schemas and data validation models for tryout."""

from datetime import datetime
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


class MeetingStatus(str, Enum):
    """Where a transcript sits in the ingest -> extract pipeline."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


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


class FileCategory(str, Enum):
    MANIFEST = "MANIFEST"
    CONFIG = "CONFIG"
    MODEL = "MODEL"
    ROUTE = "ROUTE"
    INTEGRATION = "INTEGRATION"
    ENTRYPOINT = "ENTRYPOINT"
    DOC = "DOC"
    OTHER = "OTHER"


class ScannedFile(BaseModel):
    path: str
    category: FileCategory
    size_bytes: int = 0
    content: str = ""
    truncated: bool = False


class RepoSkeleton(BaseModel):
    repo_name: str = ""
    root_path: str = ""
    files: list[ScannedFile] = Field(default_factory=list)
    tree: str = ""
    context_string: str = ""

    @property
    def manifests(self) -> list[ScannedFile]:
        return [f for f in self.files if f.category == FileCategory.MANIFEST]

    @property
    def configs(self) -> list[ScannedFile]:
        return [f for f in self.files if f.category == FileCategory.CONFIG]

    @property
    def models(self) -> list[ScannedFile]:
        return [f for f in self.files if f.category == FileCategory.MODEL]

    @property
    def routes(self) -> list[ScannedFile]:
        return [f for f in self.files if f.category == FileCategory.ROUTE]

    @property
    def integrations(self) -> list[ScannedFile]:
        return [f for f in self.files if f.category == FileCategory.INTEGRATION]

    @property
    def entrypoints(self) -> list[ScannedFile]:
        return [f for f in self.files if f.category == FileCategory.ENTRYPOINT]

    @property
    def docs(self) -> list[ScannedFile]:
        return [f for f in self.files if f.category == FileCategory.DOC]


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


class RepositorySchema(BaseModel):
    id: int | None = None
    name: str
    source: str
    source_type: RepoSource = RepoSource.LOCAL
    source_ref: str | None = None
    catalog: ArchitectureCatalog | None = None
    catalog_generated_at: datetime | None = None
    created_at: datetime | None = None


class MeetingSchema(BaseModel):
    id: int | None = None
    title: str
    occurred_at: datetime | None = None
    external_source: MeetingSource = MeetingSource.PASTE
    external_id: str | None = None
    external_url: str | None = None
    transcript: str
    minutes: MeetingMinutes | None = None
    status: MeetingStatus = MeetingStatus.PENDING
    created_at: datetime | None = None


class IdeaSchema(BaseModel):
    id: int | None = None
    meeting_id: int
    title: str
    description: str = ""
    source_quote: str = ""
    speaker: str = ""
    # Offset into the transcript ("00:12:30"), not a wall-clock time.
    timestamp: str = ""
    urgency: str = ""
    feasibility_hypothesis: str = ""
    fingerprint: str = ""
    duplicate_of_id: int | None = None
    status: IdeaStatus = IdeaStatus.PENDING
    created_at: datetime | None = None


class AttemptSchema(BaseModel):
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
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None


class FrictionLogSchema(BaseModel):
    id: int | None = None
    attempt_id: int
    category: FrictionCategory
    service_name: str = ""
    owning_team: str = ""
    mock_implementation_path: str = ""
    required_action: str = ""
    readiness_checklist: list[ReadinessItem] = Field(default_factory=list)
    created_at: datetime | None = None


# Backward-compatible aliases
Repository = RepositorySchema
Meeting = MeetingSchema
Idea = IdeaSchema
Attempt = AttemptSchema
FrictionLog = FrictionLogSchema
