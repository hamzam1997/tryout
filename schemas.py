"""Pydantic schemas and data validation models for tryout."""

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
    name: str = Field(description="Name of the data model or entity class")
    fields: list[str] = Field(
        default_factory=list,
        description="Field or attribute names belonging to this model",
    )


class RouteEntry(BaseModel):
    method: str = Field(
        default="",
        description="HTTP method (e.g. GET, POST, PUT, DELETE)",
    )
    path: str = Field(description="API endpoint route path pattern")
    handler: str = Field(
        default="",
        description="Handler function or controller name handling this route",
    )


class IntegrationEntry(BaseModel):
    name: str = Field(
        description="Name of the external service or third-party integration",
    )
    auth: str = Field(
        default="",
        description="Authentication type or mechanism (e.g. API Key, Bearer Token, OAuth)",
    )
    env_keys: list[str] = Field(
        default_factory=list,
        description="Environment variable names required for this integration",
    )


class ArchitectureCatalog(BaseModel):
    name: str = Field(
        default="",
        description="Name of the repository or service",
    )
    language: str = Field(
        default="",
        description="Primary programming language (e.g. Python, TypeScript)",
    )
    framework: str = Field(
        default="",
        description="Web or application framework (e.g. Flask, FastAPI, Django, Express)",
    )
    summary: str = Field(
        default="",
        description="High-level architecture and responsibility summary",
    )
    internal_models: list[ModelEntry] = Field(
        default_factory=list,
        description="Internal data models, entities, and database schemas with their field names",
    )
    api_routes: list[RouteEntry] = Field(
        default_factory=list,
        description="HTTP/API endpoints, HTTP methods, and corresponding controller handlers",
    )
    external_integrations: list[IntegrationEntry] = Field(
        default_factory=list,
        description="External third-party services, APIs, databases, or payment gateways with required env keys",
    )
    config_keys: list[str] = Field(
        default_factory=list,
        description="Configuration environment variable keys or settings required by the application",
    )
    config_schema: list[str] = Field(
        default_factory=list,
        description="Backward-compatible alias for config_keys",
    )
    codeowners: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of file paths/directories to owning teams or engineers (from CODEOWNERS)",
    )

    def model_post_init(self, __context) -> None:
        if not self.config_keys and self.config_schema:
            self.config_keys = list(self.config_schema)
        elif not self.config_schema and self.config_keys:
            self.config_schema = list(self.config_keys)


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
    catalog_generated_at: str | None = None
    created_at: str | None = None


class MeetingSchema(BaseModel):
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


class IdeaSchema(BaseModel):
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
    started_at: str | None = None
    finished_at: str | None = None
    created_at: str | None = None


class FrictionLogSchema(BaseModel):
    id: int | None = None
    attempt_id: int
    category: FrictionCategory
    service_name: str = ""
    owning_team: str = ""
    mock_implementation_path: str = ""
    required_action: str = ""
    readiness_checklist: list[ReadinessItem] = Field(default_factory=list)
    created_at: str | None = None


# Backward-compatible aliases
Repository = RepositorySchema
Meeting = MeetingSchema
Idea = IdeaSchema
Attempt = AttemptSchema
FrictionLog = FrictionLogSchema
