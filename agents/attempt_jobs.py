"""Background planning and patch generation for approved ideas."""

from __future__ import annotations

import logging
import shutil
import tempfile
import contextvars
import threading
from datetime import datetime, timezone
from pathlib import Path

import database as db

from agents.friction_classifier import readiness_markdown, record_friction
from agents.harness import AttemptHarness
from agents.planner import generate_plan
from agents.git_utils import fetch_github_repository
from agents.github_pr import create_attempt_pull_request
from agents.repo_onboarder import compute_source_ref
from config import settings
from integrations.mock_notifications import MockNotificationsService
from logging_setup import log_event
from schemas import AttemptStatus, AttemptStep, IdeaStatus, RepoSource, TechnicalPlan

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
    # Keep Git metadata in the isolated copy so generated changes can be
    # committed to a branch and pushed as a pull request. The scanner and
    # model-context builder skip hidden paths, so `.git` is never sent to the LLM.
    source_git = source_path / ".git"
    destination_git = destination / ".git"
    if source_git.is_dir() and not destination_git.exists():
        shutil.copytree(source_git, destination_git, symlinks=True)
    return destination, commit_sha


def _plan(attempt, idea, catalog) -> TechnicalPlan | None:
    """Plan before coding; the attempt still runs (unplanned) if planning fails."""
    meeting = db.get_meeting(idea.meeting_id)
    try:
        plan = generate_plan(idea, meeting, catalog, settings.model_planning)
    except Exception:
        logger.exception("Planning failed for attempt %s", attempt.id)
        return None
    attempt.plan = plan
    attempt.events.append(AttemptStep(
        timestamp=datetime.now(timezone.utc),
        action="plan",
        detail=f"{len(plan.repo_changes)} repo change(s), "
        f"{len(plan.external_requirements)} external requirement(s)",
    ))
    db.update_attempt(attempt)
    return plan


def notify_attempt_completion(
    attempt_id: int,
    notifications_client: MockNotificationsService | None = None,
) -> dict | None:
    """Send an automated Slack notification with attempt report URL and friction summary."""
    try:
        client = notifications_client or MockNotificationsService(
            bot_token=settings.slack_bot_token,
            default_channel=settings.slack_channel,
            service_url=settings.notifications_service_url,
            base_url=settings.app_base_url,
        )
        attempt = db.get_attempt(attempt_id)
        if attempt is None:
            return None
        idea = db.get_idea(attempt.idea_id)
        friction_logs = db.list_friction_logs(attempt_id=attempt_id)
        response = client.send_attempt_notification(
            attempt=attempt,
            idea=idea,
            friction_logs=friction_logs,
        )
        log_event(
            logger,
            "attempt_jobs.slack_notification_sent",
            attempt_id=attempt_id,
            notification_id=response.get("notification_id"),
            status=response.get("status"),
        )
        return response
    except Exception as exc:
        logger.exception("Failed to dispatch completion notification for attempt %s: %s", attempt_id, exc)
        return None


def execute_attempt(
    attempt_id: int,
    github_token: str | None = None,
    notifications_client: MockNotificationsService | None = None,
) -> None:
    attempt = db.get_attempt(attempt_id)
    if attempt is None:
        return
    idea = None
    try:
        idea = db.get_idea(attempt.idea_id)
        repo = db.get_repository(attempt.repository_id)
        if not idea or not repo or not repo.catalog:
            raise RuntimeError("Attempt is missing its idea or repository catalog.")

        db.set_attempt_status(attempt_id, AttemptStatus.PLANNING)
        attempt = db.get_attempt(attempt_id) or attempt
        with tempfile.TemporaryDirectory(prefix=f"tryout-attempt-{attempt_id}-") as temp_dir:
            workspace = Path(temp_dir) / "repository"
            workspace.mkdir()
            workspace, repo_ref = _copy_source(repo, github_token, workspace)
            attempt.repo_ref = repo_ref
            db.update_attempt(attempt)

            plan = _plan(attempt, idea, repo.catalog)

            db.set_attempt_status(attempt_id, AttemptStatus.CODING)
            attempt = db.get_attempt(attempt_id) or attempt
            harness = AttemptHarness(
                workspace=workspace,
                catalog=repo.catalog,
                idea=idea,
                attempt=attempt,
                plan=plan,
            )
            harness_result = harness.run()
            
            attempt = db.get_attempt(attempt_id) or attempt
            attempt.diff = harness_result.diff
            attempt.test_stdout = harness_result.testing_notes
            attempt.test_exit_code = harness_result.test_exit_code
            attempt.test_stderr = (
                "" if harness_result.test_exit_code == 0 else harness_result.test_output
            ) or ("" if harness_result.success else "Harness run failed or timed out.")
            db.update_attempt(attempt)

            readiness_md = ""
            if attempt.diff:
                friction = record_friction(
                    attempt, idea, repo.catalog, attempt.diff,
                    harness_result.testing_notes, settings.model_planning,
                )
                readiness_md = readiness_markdown(friction)
                attempt.events.append(AttemptStep(
                    timestamp=datetime.now(timezone.utc),
                    action="friction",
                    detail=f"{len(friction)} blocker(s) recorded",
                ))
                db.update_attempt(attempt)
                try:
                    # Parse modified files from git diff
                    import subprocess
                    diff_output = subprocess.run(["git", "diff", "--staged", "--name-only"], cwd=workspace, capture_output=True, text=True).stdout.strip()
                    change_paths = [p for p in diff_output.splitlines() if p]
                    
                    published = create_attempt_pull_request(
                        root=workspace,
                        repository_source=repo.source,
                        token=github_token,
                        attempt_id=attempt.id,
                        idea_id=idea.id,
                        idea_title=harness_result.pr_title,
                        summary=harness_result.summary[:2500] + readiness_md,
                        repo_ref=repo_ref,
                        change_paths=change_paths,
                        test_exit_code=harness_result.test_exit_code,
                    )
                except Exception as exc:
                    logger.exception("Could not publish PR for attempt %s", attempt_id)
                    attempt.test_stderr = f"Pull request creation failed: {exc}"
                    db.update_attempt(attempt)
                    published = None
                if published:
                    attempt.branch_name, attempt.base_branch, attempt.pull_request_url = published
                    db.update_attempt(attempt)
                else:
                    attempt.test_stdout += (
                        " No GitHub remote was available, so the patch is stored here "
                        "without a hosted pull request."
                    )
                    db.update_attempt(attempt)

        db.set_attempt_status(attempt_id, AttemptStatus.COMPLETE)
        idea.status = IdeaStatus.DONE
        db.update_idea(idea)
        log_event(logger, "attempt_jobs.completed", attempt_id=attempt_id, idea_id=attempt.idea_id)
        notify_attempt_completion(attempt_id, notifications_client=notifications_client)
    except Exception as exc:
        logger.exception("Attempt %s completed with a limitation: %s", attempt_id, exc)
        attempt = db.get_attempt(attempt_id) or attempt
        limitation = f"Attempt limitation: {exc}"
        attempt.test_stdout = "\n".join(
            part for part in (attempt.test_stdout, limitation) if part
        )
        db.update_attempt(attempt)
        db.set_attempt_status(attempt_id, AttemptStatus.COMPLETE)
        if idea is None:
            idea = db.get_idea(attempt.idea_id)
        if idea:
            idea.status = IdeaStatus.DONE
            db.update_idea(idea)
        log_event(
            logger,
            "attempt_jobs.completed_with_limitations",
            level=logging.WARNING,
            attempt_id=attempt_id,
            idea_id=attempt.idea_id,
            error=str(exc),
        )
        notify_attempt_completion(attempt_id, notifications_client=notifications_client)


def queue_attempt(
    attempt_id: int,
    github_token: str | None = None,
    notifications_client: MockNotificationsService | None = None,
) -> None:
    """Start the attempt worker without blocking the approval request."""
    worker = threading.Thread(
        # copy_context: the job runs in the starting request's workspace
        target=contextvars.copy_context().run,
        args=(execute_attempt, attempt_id, github_token, notifications_client),
        name=f"idea-attempt-{attempt_id}",
        daemon=True,
    )
    worker.start()
