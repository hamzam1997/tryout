"""Repository onboarding and architecture catalog endpoints."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from flask import Blueprint, jsonify, request, session

import database as db
from agents.git_utils import parse_github_slug
from agents.repo_onboarder import RepoOnboarder
from config import BASE_DIR, settings
from schemas import ArchitectureCatalog, RepoSource, Repository

logger = logging.getLogger(__name__)

bp = Blueprint("repositories", __name__, url_prefix="/repositories")

DEMO_REPO_PATH = BASE_DIR / "demo_repo" / "acme_store"


def _serialise_repo(repo: Repository, include_catalog: bool = True) -> dict:
    data = repo.model_dump(mode="json")
    if not include_catalog:
        data.pop("catalog", None)
    return data


@bp.get("")
def list_repositories():
    """List all onboarded repositories."""
    repos = db.list_repositories()
    return jsonify([_serialise_repo(r, include_catalog=True) for r in repos])


@bp.get("/<int:repo_id>")
def get_repository(repo_id: int):
    """Get single repository details with catalog."""
    repo = db.get_repository(repo_id)
    if not repo:
        return jsonify({"error": f"Repository {repo_id} not found."}), 404
    return jsonify(_serialise_repo(repo, include_catalog=True))


@bp.get("/<int:repo_id>/catalog")
def get_repository_catalog(repo_id: int):
    """Get only the ArchitectureCatalog of a repository."""
    repo = db.get_repository(repo_id)
    if not repo:
        return jsonify({"error": f"Repository {repo_id} not found."}), 404
    if not repo.catalog:
        return jsonify({"error": f"Repository {repo_id} has no generated architecture catalog."}), 404
    return jsonify(repo.catalog.model_dump(mode="json"))


def _run_demo_onboarding(repo_id: int, force_refresh: bool) -> None:
    """Background worker for Demo repo onboarding."""
    try:
        logger.info("Starting background onboarding for demo repo (id=%s)...", repo_id)
        onboarder = RepoOnboarder()
        onboarder.onboard(DEMO_REPO_PATH, force_refresh=force_refresh)
        db.set_repository_status(repo_id, "ready")
        logger.info("Demo repo onboarding complete for id=%s.", repo_id)
    except Exception as exc:
        logger.exception("Demo repo background onboarding failed for id=%s: %s", repo_id, exc)
        db.set_repository_status(repo_id, "failed", str(exc))


def _run_github_onboarding(
    repo_id: int,
    repo_slug: str,
    branch: str | None,
    token: str | None,
    force_refresh: bool,
) -> None:
    """Background worker for GitHub repo onboarding."""
    try:
        logger.info("Starting background onboarding for GitHub repo %s (id=%s)...", repo_slug, repo_id)
        onboarder = RepoOnboarder()
        onboarder.onboard_github(
            url_or_slug=repo_slug,
            branch=branch,
            access_token=token,
            force_refresh=force_refresh,
        )
        db.set_repository_status(repo_id, "ready")
        logger.info("GitHub repo onboarding complete for %s (id=%s).", repo_slug, repo_id)
    except Exception as exc:
        logger.exception("GitHub repo background onboarding failed for %s (id=%s): %s", repo_slug, repo_id, exc)
        db.set_repository_status(repo_id, "failed", str(exc))


@bp.post("/onboard")
def onboard_repository():
    """Onboard a repository asynchronously in the background.

    Returns 202 Accepted immediately. Status can be polled via GET /repositories.
    """
    body = request.get_json(silent=True) or {}
    source_type = (body.get("source_type") or "demo").lower()
    force_refresh = bool(body.get("force_refresh", False))

    if source_type in ("demo", "acme_store"):
        if not DEMO_REPO_PATH.is_dir():
            return jsonify({"error": f"Demo repository not found at {DEMO_REPO_PATH}"}), 500

        source_path = str(DEMO_REPO_PATH)
        repo = db.get_repository_by_source(source_path)
        if repo:
            db.set_repository_status(repo.id, "onboarding")
            repo = db.get_repository(repo.id)
        else:
            repo = db.create_repository(
                Repository(
                    name="acme_store",
                    source=source_path,
                    source_type=RepoSource.DEMO,
                    catalog_status="onboarding",
                )
            )

        # Launch background thread
        thread = threading.Thread(
            target=_run_demo_onboarding,
            args=(repo.id, force_refresh),
            daemon=True,
        )
        thread.start()

        return (
            jsonify(
                {
                    "message": "Demo repository onboarding started in background.",
                    "status": "onboarding",
                    "repository": _serialise_repo(repo),
                }
            ),
            202,
        )

    elif source_type == "github":
        repo_slug = (body.get("repo_full_name") or body.get("url") or "").strip()
        if not repo_slug:
            return jsonify({"error": "repo_full_name or url is required for GitHub onboarding."}), 400

        try:
            owner, repo_name = parse_github_slug(repo_slug)
        except ValueError as val_err:
            return jsonify({"error": str(val_err)}), 400

        canonical_source = f"https://github.com/{owner}/{repo_name}"
        branch = body.get("branch") or None
        token = (
            session.get("github_token")
            or request.headers.get("X-GitHub-Token")
            or None
        )

        repo = db.get_repository_by_source(canonical_source)
        if repo:
            db.set_repository_status(repo.id, "onboarding")
            repo = db.get_repository(repo.id)
        else:
            repo = db.create_repository(
                Repository(
                    name=repo_name,
                    source=canonical_source,
                    source_type=RepoSource.GITHUB,
                    catalog_status="onboarding",
                )
            )

        # Launch background thread
        thread = threading.Thread(
            target=_run_github_onboarding,
            args=(repo.id, canonical_source, branch, token, force_refresh),
            daemon=True,
        )
        thread.start()

        return (
            jsonify(
                {
                    "message": f"GitHub repository '{repo.name}' onboarding started in background.",
                    "status": "onboarding",
                    "repository": _serialise_repo(repo),
                }
            ),
            202,
        )

    else:
        return (
            jsonify(
                {
                    "error": f"Unsupported source_type '{source_type}'. Only 'github' and 'demo' are supported."
                }
            ),
            400,
        )
