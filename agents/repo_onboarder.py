"""RepoOnboarder agent for generating and caching architecture catalogs.

Uses Gemini 2.5 Flash with structured output to analyze repository skeletons
and synthesize high-fidelity ArchitectureCatalog instances, persisted to SQLite.
"""

from __future__ import annotations

import hashlib
import logging
import subprocess
from pathlib import Path
from typing import overload

from google import genai
from google.genai import types

import database as db
from config import settings
from llm import get_client
from repo_scanner import RepoSkeleton, scan_repo
from schemas import ArchitectureCatalog, RepoSource, Repository

logger = logging.getLogger(__name__)

REPO_ONBOARDER_SYSTEM_INSTRUCTION = """You are an expert Principal Software Architect and Repository Onboarding Agent.
Your task is to analyze an architectural code skeleton of a software repository and synthesize a rich, high-fidelity ArchitectureCatalog designed to guide AI planning and coding agents.

You must extract:
1. name: Name of the repository or service.
2. language: Primary programming language (e.g., Python, TypeScript, Go).
3. framework: The primary web or application framework used (e.g., Flask, FastAPI, Django, Express, Next.js).
4. entrypoint: Main application entrypoint file (e.g., app.py, main.py, server.ts).
5. test_command: Command to execute the automated test suite (e.g., python -m unittest discover -s tests, pytest, npm test).
6. summary: A concise architectural overview explaining what this service does and its core domain logic.
7. dependencies: Primary external packages and libraries used (e.g. from requirements.txt, package.json).
8. modules: The 3 to 7 primary architectural modules / subsystems dividing the repository domain. For each module provide:
   - name: Clear title of the subsystem (e.g. Orders & Checkout, Payments Adapter, Logistics & Shifts).
   - path: Primary directory path or key file location (e.g. routes/orders.py, src/libdispatch/).
   - description: What this module does and the business domain it encapsulates.
   - responsibilities: Bullet list of specific jobs or capabilities handled by this module.
   - key_files: Main files belonging to this module.
   - owner: Owning team or codeowner handle (e.g. @team-orders, @team-payments).
9. key_files: Key architectural files and their responsibilities.
10. internal_models: All internal business entities, data models, and database schemas with:
   - name: Entity name (e.g. Order, Customer).
   - file_path: File where it is defined.
   - description: Domain meaning and purpose.
   - fields: List of field/attribute names.
11. api_routes: All HTTP/API endpoints with:
   - method: HTTP method (GET, POST, PUT, DELETE, etc.).
   - path: Route pattern (e.g. /orders, /refunds).
   - handler: Controller or handler function name.
   - file_path: File where the route is implemented.
   - description: What this endpoint accomplishes.
12. external_integrations: All third-party services, APIs, payment gateways, message queues, or external services called by the codebase, with:
   - name: Service name.
   - file_path: Adapter or client file path.
   - description: Purpose of integration.
   - auth: Authentication mechanism.
   - env_keys: Environment variable keys required.
13. external_dependencies: Any known external services or microservices referenced or mentioned outside this repository (such as notifications service owned by @team-comms).
14. config_keys: All configuration keys and environment variables required by the application.
15. codeowners: Mapping of file path patterns or directories to owning teams/engineers from CODEOWNERS files.
16. coding_guidelines: Key conventions, testing practices, and patterns for coding agents working in this repository.

Rules:
- Group the codebase into logical architectural modules/subsystems so planning agents understand domain boundaries.
- Rely strictly on evidence in the provided skeleton files and directory tree.
- Ensure every detected model and route indicates the file where it is defined.
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
                # Structured JSON schema is not tool use; disable AFC to avoid
                # the SDK warning that generate_content + AFC is discouraged.
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                ),
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

        # Enrich modules with owners from codeowners if missing
        if catalog.codeowners and catalog.modules:
            for mod in catalog.modules:
                if not mod.owner:
                    for pattern, owner in catalog.codeowners.items():
                        clean_pat = pattern.lstrip("/")
                        if mod.path == clean_pat or mod.path.startswith(clean_pat.rstrip("/")):
                            mod.owner = owner
                            break

        # Enrich key_files with owners from codeowners if missing
        if catalog.codeowners and catalog.key_files:
            for kf in catalog.key_files:
                if not kf.owner:
                    for pattern, owner in catalog.codeowners.items():
                        clean_pat = pattern.lstrip("/")
                        if kf.path == clean_pat or kf.path.startswith(clean_pat.rstrip("/")):
                            kf.owner = owner
                            break

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
            repo_str = str(repo).strip()
            if repo_str.startswith(("https://github.com", "http://github.com", "git@github.com")):
                return self.onboard_github(
                    repo_str,
                    force_refresh=force_refresh,
                    source_ref=source_ref,
                    return_repo=return_repo,
                )
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

    def onboard_github(
        self,
        url_or_slug: str,
        branch: str | None = None,
        access_token: str | None = None,
        force_refresh: bool = False,
        source_ref: str | None = None,
        return_repo: bool = False,
    ) -> ArchitectureCatalog | tuple[Repository, ArchitectureCatalog]:
        """Onboard a GitHub repository by fetching it via OAuth token and generating/caching its catalog."""
        from agents.git_utils import fetch_github_repository, parse_github_slug

        owner, repo_name = parse_github_slug(url_or_slug)
        canonical_source = f"https://github.com/{owner}/{repo_name}"

        found = db.get_repository_by_source(canonical_source)
        if found:
            repo_obj = found
        else:
            repo_obj = db.create_repository(
                Repository(
                    name=repo_name,
                    source=canonical_source,
                    source_type=RepoSource.GITHUB,
                )
            )

        # Fetch/clone the repository locally
        local_path, commit_sha, _ = fetch_github_repository(
            url_or_slug=canonical_source,
            branch=branch,
            access_token=access_token,
            force_refresh=force_refresh,
        )
        effective_ref = source_ref or commit_sha

        # Check cache freshness against the commit SHA
        if not force_refresh and repo_obj.catalog is not None:
            if repo_obj.source_ref == effective_ref:
                logger.info(
                    "Reusing cached architecture catalog for GitHub repo %s (%s)",
                    repo_obj.name,
                    effective_ref[:8],
                )
                if return_repo:
                    return repo_obj, repo_obj.catalog
                return repo_obj.catalog

        # Cache miss or forced refresh: scan and generate catalog
        logger.info(
            "Scanning and generating architecture catalog for GitHub repo %s (%s)",
            repo_obj.name,
            effective_ref[:8],
        )
        skeleton = scan_repo(local_path)
        catalog = self.generate_catalog(skeleton)
        if not catalog.name:
            catalog.name = repo_obj.name

        db.save_catalog(repo_obj.id, catalog, source_ref=effective_ref)
        updated_repo = db.get_repository(repo_obj.id)
        if not updated_repo:
            raise RuntimeError(f"Failed to reload repository {repo_obj.id}")

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
