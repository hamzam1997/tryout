"""RepoOnboarder agent for generating and caching architecture catalogs.

Uses Gemini 2.5 Flash with structured output to analyze repository skeletons
and synthesize high-fidelity ArchitectureCatalog instances, persisted to SQLite.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
import subprocess
from typing import TYPE_CHECKING, overload

from google import genai
from google.genai import types

from config import settings
import database as db
from llm import get_client
from repo_scanner import RepoSkeleton, scan_repo
from schemas import (
    ArchitectureCatalog,
    IntegrationEntry,
    ModelEntry,
    RepoSkeleton as RepoSkeletonSchema,
    RepoSource,
    Repository,
    RouteEntry,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

REPO_ONBOARDER_SYSTEM_INSTRUCTION = """You are an expert Principal Software Architect and Repository Onboarding Agent.
Your task is to analyze an architectural code skeleton of a software repository and synthesize a structured ArchitectureCatalog.

You must extract:
1. name: Name of the repository or service.
2. language: Primary programming language (e.g., Python, TypeScript, Go).
3. framework: The primary web or application framework used (e.g., Flask, FastAPI, Django, Express, Next.js).
4. summary: A concise architectural overview explaining what this service does and its core domain logic.
5. internal_models: All internal business entities, data models, and database schemas with their field names.
6. api_routes: All HTTP/API routes with HTTP method (GET, POST, PUT, DELETE, etc.), route path, and handler function name.
7. external_integrations: All third-party services, external APIs, payment gateways, message queues, or external services called, including their authentication mechanism and required environment variable keys.
8. config_keys: All configuration keys and environment variables required by the application (e.g. from .env.example, config files, or os.getenv).
9. codeowners: Mapping of file path patterns or directories to owning teams/engineers from CODEOWNERS files.

Rules:
- Rely strictly on evidence in the provided skeleton files and directory tree.
- Do not invent models, endpoints, or integrations not evidenced in the repository.
- Ensure every detected model includes its relevant field names.
- Ensure every route includes its HTTP method and path pattern.
"""


def compute_source_ref(repo_path: Path | str) -> str:
    """Compute a reference fingerprint for a repository path.

    Uses git rev-parse HEAD if .git exists, otherwise falls back to a deterministic
    SHA256 checksum over scanned files and metadata.
    """
    path = Path(repo_path).resolve()
    git_dir = path / ".git"
    if git_dir.exists():
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=path,
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            sha = res.stdout.strip()
            if sha:
                return sha
        except Exception:
            pass

    hasher = hashlib.sha256()
    hasher.update(path.name.encode("utf-8"))
    try:
        for file in sorted(path.rglob("*")):
            if file.is_file() and not any(
                part.startswith(".") for part in file.relative_to(path).parts
            ):
                hasher.update(str(file.relative_to(path)).encode("utf-8"))
                stat = file.stat()
                hasher.update(str(stat.st_size).encode("utf-8"))
                hasher.update(str(stat.st_mtime_ns).encode("utf-8"))
    except OSError:
        pass

    return hasher.hexdigest()[:16]


def extract_codeowners_from_skeleton(skeleton: RepoSkeleton) -> dict[str, str]:
    """Parse CODEOWNERS entries from any config files present in the skeleton."""
    codeowners: dict[str, str] = {}
    for cfg in skeleton.configs:
        if "codeowners" in cfg.path.lower():
            for line in cfg.content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    codeowners[parts[0]] = parts[1]
    return codeowners


class RepoOnboarder:
    """Agent responsible for onboarding codebases and generating Architecture Catalogs."""

    def __init__(
        self,
        client: genai.Client | None = None,
        model: str | None = None,
    ) -> None:
        self._client = client
        self.model = model or settings.model_onboarding

    @property
    def client(self) -> genai.Client:
        """Lazily initialize the Vertex AI client if not injected."""
        if self._client is None:
            self._client = get_client()
        return self._client

    def generate_catalog(
        self,
        skeleton: RepoSkeleton | str | Path,
    ) -> ArchitectureCatalog:
        """Synthesize an ArchitectureCatalog from a repository skeleton using Gemini 2.5 Flash."""
        if isinstance(skeleton, (str, Path)):
            skeleton_obj = scan_repo(skeleton)
        else:
            skeleton_obj = skeleton

        prompt = (
            f"Analyze the following repository code skeleton and synthesize its architecture catalog:\n\n"
            f"{skeleton_obj.context_string}"
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=REPO_ONBOARDER_SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=ArchitectureCatalog,
                temperature=0.1,
            ),
        )

        if not response or not response.text:
            raise ValueError("Empty or null response received from Gemini model.")

        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()

        catalog = ArchitectureCatalog.model_validate_json(raw_text)

        # Fallback enrichment
        if not catalog.name and skeleton_obj.repo_name:
            catalog.name = skeleton_obj.repo_name

        if not catalog.codeowners:
            fallback_codeowners = extract_codeowners_from_skeleton(skeleton_obj)
            if fallback_codeowners:
                catalog.codeowners = fallback_codeowners

        return catalog

    @overload
    def onboard(
        self,
        repo: Repository | int | str | Path,
        force_refresh: bool = False,
        source_ref: str | None = None,
        return_repo: bool = False,
    ) -> ArchitectureCatalog: ...

    @overload
    def onboard(
        self,
        repo: Repository | int | str | Path,
        force_refresh: bool = False,
        source_ref: str | None = None,
        return_repo: bool = True,
    ) -> tuple[Repository, ArchitectureCatalog]: ...

    def onboard(
        self,
        repo: Repository | int | str | Path,
        force_refresh: bool = False,
        source_ref: str | None = None,
        return_repo: bool = False,
    ) -> ArchitectureCatalog | tuple[Repository, ArchitectureCatalog]:
        """Onboard a repository, ensuring one-time caching of the ArchitectureCatalog.

        If a cached catalog exists in SQLite for the current repository state and
        force_refresh is False, the cached catalog is returned immediately without
        calling Gemini.
        """
        # Resolve repository database entity
        repo_obj: Repository
        if isinstance(repo, int):
            found = db.get_repository(repo)
            if not found:
                raise ValueError(f"Repository with ID {repo} not found in database.")
            repo_obj = found
        elif isinstance(repo, Repository):
            if repo.id is not None:
                found = db.get_repository(repo.id)
                repo_obj = found if found else repo
            else:
                repo_obj = db.get_or_create_repository(repo)
        elif isinstance(repo, (str, Path)):
            resolved_path = str(Path(repo).resolve())
            found = db.get_repository_by_source(resolved_path)
            if found:
                repo_obj = found
            else:
                repo_name = Path(resolved_path).name
                repo_obj = db.create_repository(
                    Repository(
                        name=repo_name,
                        source=resolved_path,
                        source_type=RepoSource.LOCAL,
                    )
                )
        else:
            raise TypeError(f"Unsupported repository type: {type(repo)}")

        # Check existing catalog cache
        effective_ref = source_ref or compute_source_ref(repo_obj.source)

        if not force_refresh and repo_obj.catalog is not None:
            # If repo has source_ref, check freshness; if not, any existing catalog is reused
            if repo_obj.source_ref is None or repo_obj.source_ref == effective_ref:
                logger.info(
                    "Reusing cached architecture catalog for repository '%s' (id=%s)",
                    repo_obj.name,
                    repo_obj.id,
                )
                if return_repo:
                    return repo_obj, repo_obj.catalog
                return repo_obj.catalog

        # Cache miss or forced refresh: scan and generate catalog
        logger.info(
            "Generating new architecture catalog for repository '%s' (id=%s)",
            repo_obj.name,
            repo_obj.id,
        )
        skeleton = scan_repo(repo_obj.source)
        catalog = self.generate_catalog(skeleton)

        if not catalog.name:
            catalog.name = repo_obj.name or skeleton.repo_name

        # Persist generated catalog into database linked to repository
        db.save_catalog(repo_obj.id, catalog, source_ref=effective_ref)
        updated_repo = db.get_repository(repo_obj.id)
        if not updated_repo:
            raise RuntimeError(f"Failed to reload repository {repo_obj.id} after saving catalog.")

        if return_repo:
            return updated_repo, catalog
        return catalog

    def get_catalog(self, repo_id: int) -> ArchitectureCatalog | None:
        """Fetch cached architecture catalog for a repository ID, if one exists."""
        repo = db.get_repository(repo_id)
        return repo.catalog if repo else None


def onboard_repository(
    repo: Repository | int | str | Path,
    force_refresh: bool = False,
    source_ref: str | None = None,
    client: genai.Client | None = None,
) -> ArchitectureCatalog:
    """Convenience helper to onboard a repository and return its ArchitectureCatalog."""
    onboarder = RepoOnboarder(client=client)
    return onboarder.onboard(repo, force_refresh=force_refresh, source_ref=source_ref)


def generate_architecture_catalog(
    skeleton: RepoSkeleton | str | Path,
    client: genai.Client | None = None,
) -> ArchitectureCatalog:
    """Convenience helper to generate an ArchitectureCatalog from a repository skeleton."""
    onboarder = RepoOnboarder(client=client)
    return onboarder.generate_catalog(skeleton)
