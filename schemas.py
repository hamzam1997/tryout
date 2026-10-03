"""Domain DTOs and enums shared by agents, API, and persistence."""

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


class IdeasExtractStatus(str, Enum):
    """Background idea extraction for a meeting after minutes are ready."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class IdeaStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    IN_PROCESS = "IN_PROCESS"
    REJECTED = "REJECTED"


class AttemptStatus(str, Enum):
    QUEUED = "QUEUED"
    PLANNING = "PLANNING"
    CODING = "CODING"
    TESTING = "TESTING"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
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


class ModuleDescription(BaseModel):
    name: str = Field(description="Name or title of the module or subsystem (e.g. Orders & Checkout, Payments Adapter)")
    path: str = Field(description="Directory path or primary file location (e.g. routes/orders.py, src/libdispatch/)")
    description: str = Field(description="High-level purpose and business domain of this module")
    responsibilities: list[str] = Field(
        default_factory=list,
        description="Key capabilities and tasks handled by this module",
    )
    key_files: list[str] = Field(
        default_factory=list,
        description="Primary files belonging to this module",
    )
    owner: str = Field(default="", description="Owning team or codeowner handle (from CODEOWNERS)")


class FileRole(BaseModel):
    path: str = Field(description="Relative file path in the repository (e.g. routes/orders.py)")
    role: str = Field(description="Architectural role and primary responsibilities of this file")
    owner: str = Field(default="", description="Owning team or codeowner responsible for this file")


class ModelEntry(BaseModel):
    name: str = Field(description="Name of the data model or entity class")
    file_path: str = Field(default="", description="File where this model is defined (e.g. models.py)")
    description: str = Field(default="", description="Description of the entity and its domain purpose")
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
    file_path: str = Field(default="", description="File where this route handler is implemented")
    description: str = Field(default="", description="Summary of what this endpoint does")


class IntegrationEntry(BaseModel):
    name: str = Field(
        description="Name of the external service or third-party integration",
    )
    file_path: str = Field(default="", description="File where this client or integration adapter is defined")
    description: str = Field(default="", description="Purpose of integration and operations performed")
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
    entrypoint: str = Field(
        default="",
        description="Main entrypoint file to run the service (e.g. app.py)",
    )
    test_command: str = Field(
        default="",
        description="Command to run the automated test suite (e.g. python -m unittest discover -s tests)",
    )
    summary: str = Field(
        default="",
        description="High-level architecture and responsibility summary",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="Primary libraries and package dependencies (e.g. Flask, requests)",
    )
    modules: list[ModuleDescription] = Field(
        default_factory=list,
        description="Architectural modules and subsystems dividing the repository domain",
    )
    key_files: list[FileRole] = Field(
        default_factory=list,
        description="Key architectural files, their responsibilities, and owning teams",
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
    external_dependencies: list[str] = Field(
        default_factory=list,
        description="Known external services or systems called or referenced outside this repository (e.g. separate microservices)",
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
    coding_guidelines: list[str] = Field(
        default_factory=list,
        description="Key conventions, testing practices, and patterns for coding agents working in this repo",
    )

    def to_markdown(self) -> str:
        """Render a readable markdown summary of the architecture catalog."""
        lines: list[str] = [
            f"# Architecture Catalog: {self.name or 'Application'}",
            "",
            "## Overview",
            f"- **Primary Language:** {self.language or 'Not specified'}",
            f"- **Framework:** {self.framework or 'Not specified'}",
            f"- **Entrypoint:** `{self.entrypoint}`" if self.entrypoint else "- **Entrypoint:** Not specified",
            f"- **Test Command:** `{self.test_command}`" if self.test_command else "- **Test Command:** Not specified",
            f"- **Summary:** {self.summary}",
            "",
        ]

        if self.dependencies:
            lines.extend([
                "## Dependencies",
                ", ".join(f"`{d}`" for d in self.dependencies),
                "",
            ])

        if self.modules:
            lines.extend(["## Architectural Modules & Subsystems", ""])
            for mod in self.modules:
                owner_str = f" ({mod.owner})" if mod.owner else ""
                lines.append(f"### {mod.name}{owner_str}")
                lines.append(f"- **Path:** `{mod.path}`")
                lines.append(f"- **Description:** {mod.description}")
                if mod.responsibilities:
                    lines.append(f"- **Responsibilities:** {', '.join(mod.responsibilities)}")
                if mod.key_files:
                    lines.append(f"- **Key Files:** {', '.join(f'`{f}`' for f in mod.key_files)}")
                lines.append("")

        if self.key_files:
            lines.extend(["## Key Files", ""])
            for f in self.key_files:
                owner_str = f" ({f.owner})" if f.owner else ""
                lines.append(f"- **`{f.path}`**{owner_str}: {f.role}")
            lines.append("")

        if self.internal_models:
            lines.extend(["## Data Models & Schemas", ""])
            for m in self.internal_models:
                loc = f" (`{m.file_path}`)" if m.file_path else ""
                desc = f": {m.description}" if m.description else ""
                fields = f" (Fields: {', '.join(m.fields)})" if m.fields else ""
                lines.append(f"- **`{m.name}`**{loc}{desc}{fields}")
            lines.append("")

        if self.api_routes:
            lines.extend(["## API Routes", ""])
            for r in self.api_routes:
                method = r.method or "ANY"
                handler_str = f" -> `{r.handler}`" if r.handler else ""
                loc = f" (`{r.file_path}`)" if r.file_path else ""
                desc = f" — {r.description}" if r.description else ""
                lines.append(f"- **`{method} {r.path}`**{handler_str}{loc}{desc}")
            lines.append("")

        if self.external_integrations or self.external_dependencies:
            lines.extend(["## External Integrations & Services", ""])
            for i in self.external_integrations:
                loc = f" (`{i.file_path}`)" if i.file_path else ""
                auth = f", Auth: {i.auth}" if i.auth else ""
                envs = f", Env: {', '.join(i.env_keys)}" if i.env_keys else ""
                desc = f": {i.description}" if i.description else ""
                lines.append(f"- **{i.name}**{loc}{auth}{envs}{desc}")
            if self.external_dependencies:
                lines.append("- **External services outside repository:**")
                for ext in self.external_dependencies:
                    lines.append(f"  - {ext}")
            lines.append("")

        if self.config_keys:
            lines.extend([
                "## Configuration Keys (.env)",
                ", ".join(f"`{k}`" for k in self.config_keys),
                "",
            ])

        if self.coding_guidelines:
            lines.extend(["## Coding & Testing Guidelines", ""])
            for rule in self.coding_guidelines:
                lines.append(f"- {rule}")
            lines.append("")

        return "\n".join(lines).strip()

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


class Repository(BaseModel):
    id: int | None = None
    name: str
    source: str
    source_type: RepoSource = RepoSource.LOCAL
    source_ref: str | None = None
    catalog: ArchitectureCatalog | None = None
    catalog_status: str = "ready"
    catalog_error: str | None = None
    catalog_generated_at: datetime | None = None
    created_at: datetime | None = None


class Meeting(BaseModel):
    id: int | None = None
    title: str
    occurred_at: datetime | None = None
    external_source: MeetingSource = MeetingSource.PASTE
    external_id: str | None = None
    external_url: str | None = None
    transcript: str
    minutes: MeetingMinutes | None = None
    status: MeetingStatus = MeetingStatus.PENDING
    # Background idea extraction lifecycle (separate from minutes status).
    ideas_status: IdeasExtractStatus = IdeasExtractStatus.PENDING
    # Last idea-extraction failure for this meeting; cleared on success.
    ideas_error: str | None = None
    created_at: datetime | None = None


class ExtractedIdeaCandidate(BaseModel):
    """Gemini-facing idea before it is persisted as an Idea row."""

    title: str = ""
    description: str = ""
    quote: str = Field(default="", description="Verbatim transcript quote supporting this idea")
    speaker: str = ""
    cue_time: str = Field(
        default="",
        description="Transcript cue offset such as 00:12:30, not a wall-clock time",
    )
    priority: str = Field(default="", description="low, medium, or high")
    attempt_hypothesis: str = Field(
        default="",
        description="Catalog-grounded note of what to change in-repo and what is missing/external",
    )
    catalog_refs: list[str] = Field(
        default_factory=list,
        description="Catalog modules, routes, models, or integrations this idea would touch",
    )
    idea_key: str = Field(
        default="",
        description="Stable kebab-case key for the underlying proposal across meetings",
    )


class ExtractedIdeaBatch(BaseModel):
    ideas: list[ExtractedIdeaCandidate] = Field(default_factory=list)


class Idea(BaseModel):
    id: int | None = None
    meeting_id: int
    repository_id: int | None = None
    title: str
    description: str = ""
    quote: str = ""
    speaker: str = ""
    # Offset into the transcript ("00:12:30"), not a wall-clock time.
    cue_time: str = ""
    priority: str = ""
    attempt_hypothesis: str = ""
    catalog_refs: list[str] = Field(default_factory=list)
    idea_key: str = ""
    original_idea_id: int | None = None
    status: IdeaStatus = IdeaStatus.PENDING
    approved_by: str | None = None
    approved_at: datetime | None = None
    created_at: datetime | None = None


class Attempt(BaseModel):
    id: int | None = None
    idea_id: int
    repository_id: int
    repo_ref: str | None = None
    base_branch: str | None = None
    branch_name: str | None = None
    pull_request_url: str | None = None
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


class FrictionLog(BaseModel):
    id: int | None = None
    attempt_id: int
    category: FrictionCategory
    service_name: str = ""
    owning_team: str = ""
    mock_implementation_path: str = ""
    required_action: str = ""
    readiness_checklist: list[ReadinessItem] = Field(default_factory=list)
    created_at: datetime | None = None


class User(BaseModel):
    uid: str
    email: str | None = None
    name: str | None = None
    avatar_url: str | None = None
    provider: str | None = None
    github_login: str | None = None
    created_at: datetime | None = None
    last_login_at: datetime | None = None
