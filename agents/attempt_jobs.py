"""Background planning and patch generation for approved ideas."""

from __future__ import annotations

import logging
import shutil
import tempfile
import threading
from pathlib import Path

import database as db
from agents.attempt_agent import generate_plan
from agents.coder import CodingAgent
from agents.git_utils import fetch_github_repository
from agents.github_pr import create_attempt_pull_request
from agents.repo_onboarder import compute_source_ref
from config import settings
from logging_setup import log_event
from repo_scanner.traversal import walk_repository
from schemas import AttemptStatus, RepoSource

logger = logging.getLogger(__name__)


def _ignore_repo_items(_directory: str, names: list[str]) -> set[str]:
    ignored = {".git", ".env", "node_modules", "venv", ".venv", "__pycache__"}
    return {
        name for name in names
        if name in ignored
        or name.startswith(".env.")
        or _is_sensitive_filename(name)
    }


def _is_sensitive_filename(name: str) -> bool:
    lowered = name.lower()
    return (
        lowered in {"credentials.json", "id_rsa", "id_ed25519"}
        or any(part in lowered for part in ("credential", "secret", "private_key", "service-account"))
        or lowered.endswith((".pem", ".key", ".p12", ".pfx"))
    )


def _copy_source(repo, github_token: str | None, destination: Path) -> tuple[Path, str]:
    if repo.source_type == RepoSource.GITHUB:
        source_path, commit_sha, _ = fetch_github_repository(
            repo.source,
            access_token=github_token,
        )
        if repo.source_ref and commit_sha != repo.source_ref:
            raise RuntimeError(
                "The cached GitHub checkout no longer matches the catalog snapshot. "
                "Refresh the repository catalog before starting an attempt."
            )
    else:
        source_path = Path(repo.source).resolve()
        if not source_path.is_dir():
            raise RuntimeError(f"Repository source is unavailable: {source_path}")
        current_ref = compute_source_ref(source_path)
        if repo.source_ref and current_ref != repo.source_ref:
            raise RuntimeError(
                "The repository has changed since its architecture catalog was generated. "
                "Refresh the repository catalog before starting an attempt."
            )
        commit_sha = repo.source_ref or current_ref

    shutil.copytree(
        source_path,
        destination,
        ignore=_ignore_repo_items,
        symlinks=True,
        dirs_exist_ok=True,
    )
    return destination, commit_sha


def _relevant_context(root: Path, idea, plan, catalog) -> str:
    wanted: set[str] = set()
    refs = {ref.strip().strip("/") for ref in idea.catalog_refs if ref.strip()}
    for step in plan.repo_changes:
        if step.target:
            wanted.add(step.target.strip().strip("/"))
    for file_role in catalog.key_files:
        if any(ref in file_role.path or ref in file_role.description for ref in refs):
            wanted.add(file_role.path.strip().strip("/"))
    for module in catalog.modules:
        if any(ref in module.path or ref in module.name for ref in refs):
            wanted.add(module.path.strip().strip("/"))

    candidates = []
    for file_path, relative in walk_repository(root):
        filename = Path(relative).name.lower()
        if file_path.is_symlink() or any(part.startswith(".") for part in Path(relative).parts):
            continue
        if _is_sensitive_filename(filename):
            continue
        candidates.append((file_path, relative))

    selected = []
    for file_path, relative in candidates:
        if any(relative == path or relative.startswith(path.rstrip("/") + "/") for path in wanted):
            selected.append((file_path, relative))
    if not selected:
        selected = candidates[:10]

    parts = []
    budget = 60_000
    for path, relative in selected[:20]:
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        content = content[:8_000]
        block = f"\n--- {relative} ---\n{content}\n"
        if len(block) > budget:
            break
        parts.append(block)
        budget -= len(block)
    return "".join(parts)


def execute_attempt(attempt_id: int, github_token: str | None = None) -> None:
    attempt = db.get_attempt(attempt_id)
    if attempt is None:
        return
    try:
        idea = db.get_idea(attempt.idea_id)
        repo = db.get_repository(attempt.repository_id)
        meeting = db.get_meeting(idea.meeting_id) if idea else None
        if not idea or not repo or not meeting or not repo.catalog:
            raise RuntimeError("Attempt is missing its idea, repository catalog, or meeting context.")

        db.set_attempt_status(attempt_id, AttemptStatus.PLANNING)
        attempt = db.get_attempt(attempt_id) or attempt
        with tempfile.TemporaryDirectory(prefix=f"tryout-attempt-{attempt_id}-") as temp_dir:
            workspace = Path(temp_dir) / "repository"
            workspace.mkdir()
            workspace, repo_ref = _copy_source(repo, github_token, workspace)
            attempt.repo_ref = repo_ref
            db.update_attempt(attempt)

            plan = generate_plan(idea, meeting, repo.catalog, settings.model_planning)
            attempt.plan = plan
            db.update_attempt(attempt)

            db.set_attempt_status(attempt_id, AttemptStatus.CODING)
            attempt = db.get_attempt(attempt_id) or attempt
            context = _relevant_context(workspace, idea, plan, repo.catalog)
            batch, attempt.diff = CodingAgent(settings.model_coding).generate_and_apply(
                root=workspace,
                idea=idea,
                plan=plan,
                catalog=repo.catalog,
                source_context=context,
            )
            if not batch.changes:
                attempt.test_stdout = "No code changes were generated; review the plan and blockers."
                attempt.test_exit_code = None
            else:
                attempt.test_stdout = (
                    "Tests were not run: this deployment does not have an isolated code-execution sandbox."
                )
                attempt.test_exit_code = None
            attempt.test_stderr = ""
            db.update_attempt(attempt)

            if attempt.diff:
                published = create_attempt_pull_request(
                    root=workspace,
                    repository_source=repo.source,
                    token=github_token,
                    attempt_id=attempt.id,
                    idea_id=idea.id,
                    idea_title=idea.title,
                    summary=plan.summary,
                    repo_ref=repo_ref,
                    change_paths=[change.path for change in batch.changes],
                )
                if published:
                    attempt.branch_name, attempt.base_branch, attempt.pull_request_url = published
                    db.update_attempt(attempt)
                else:
                    attempt.test_stdout += (
                        " No GitHub remote was available, so the patch is stored here "
                        "without a hosted pull request."
                    )
                    db.update_attempt(attempt)

        db.set_attempt_status(attempt_id, AttemptStatus.READY_FOR_REVIEW)
        log_event(logger, "attempt_jobs.completed", attempt_id=attempt_id, idea_id=attempt.idea_id)
    except Exception as exc:
        logger.exception("Attempt %s failed: %s", attempt_id, exc)
        db.set_attempt_status(attempt_id, AttemptStatus.FAILED, error=str(exc))
        log_event(
            logger,
            "attempt_jobs.failed",
            level=logging.ERROR,
            attempt_id=attempt_id,
            idea_id=attempt.idea_id,
            error=str(exc),
        )


def queue_attempt(attempt_id: int, github_token: str | None = None) -> None:
    """Start the attempt worker without blocking the approval request."""
    worker = threading.Thread(
        target=execute_attempt,
        args=(attempt_id, github_token),
        name=f"idea-attempt-{attempt_id}",
        daemon=True,
    )
    worker.start()
