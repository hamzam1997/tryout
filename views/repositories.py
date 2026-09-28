"""Repository onboarding and architecture catalog endpoints."""

from __future__ import annotations

import logging
from pathlib import Path

from flask import Blueprint, jsonify, request, session

import database as db
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


@bp.post("/onboard")
def onboard_repository():
    """Onboard a repository via GitHub OAuth, Demo Repo, or Local Path."""
    body = request.get_json(silent=True) or {}
    source_type = (body.get("source_type") or "demo").lower()
    force_refresh = bool(body.get("force_refresh", False))

    onboarder = RepoOnboarder()

    try:
        if source_type in ("demo", "acme_store"):
            if not DEMO_REPO_PATH.is_dir():
                return jsonify({"error": f"Demo repository not found at {DEMO_REPO_PATH}"}), 500

            repo, catalog = onboarder.onboard(
                DEMO_REPO_PATH,
                force_refresh=force_refresh,
                return_repo=True,
            )
            return (
                jsonify(
                    {
                        "message": "Demo repository onboarded successfully.",
                        "repository": _serialise_repo(repo),
                        "catalog": catalog.model_dump(mode="json"),
                    }
                ),
                201 if force_refresh or repo.created_at else 200,
            )

        elif source_type == "github":
            repo_slug = (body.get("repo_full_name") or body.get("url") or "").strip()
            if not repo_slug:
                return jsonify({"error": "repo_full_name or url is required for GitHub onboarding."}), 400

            branch = body.get("branch") or None
            # Retrieve token from session or authorization header or fallback to environment
            token = (
                session.get("github_token")
                or request.headers.get("X-GitHub-Token")
                or None
            )

            repo, catalog = onboarder.onboard_github(
                url_or_slug=repo_slug,
                branch=branch,
                access_token=token,
                force_refresh=force_refresh,
                return_repo=True,
            )
            return (
                jsonify(
                    {
                        "message": f"GitHub repository '{repo.name}' onboarded successfully.",
                        "repository": _serialise_repo(repo),
                        "catalog": catalog.model_dump(mode="json"),
                    }
                ),
                201,
            )

        elif source_type == "local":
            path_str = (body.get("path") or "").strip()
            if not path_str:
                return jsonify({"error": "path is required for local repository onboarding."}), 400

            target = Path(path_str).resolve()
            if not target.is_dir():
                return jsonify({"error": f"Local path '{path_str}' does not exist or is not a directory."}), 400

            repo, catalog = onboarder.onboard(
                target,
                force_refresh=force_refresh,
                return_repo=True,
            )
            return (
                jsonify(
                    {
                        "message": f"Local repository '{repo.name}' onboarded successfully.",
                        "repository": _serialise_repo(repo),
                        "catalog": catalog.model_dump(mode="json"),
                    }
                ),
                201,
            )

        else:
            return jsonify({"error": f"Unsupported source_type '{source_type}'. Expected 'github', 'demo', or 'local'."}), 400

    except PermissionError as perm_err:
        logger.warning("Permission error onboarding repo: %s", perm_err)
        return jsonify({"error": str(perm_err)}), 403
    except ValueError as val_err:
        logger.warning("Validation error onboarding repo: %s", val_err)
        return jsonify({"error": str(val_err)}), 400
    except Exception as exc:
        logger.exception("Failed to onboard repository: %s", exc)
        return jsonify({"error": f"Failed to onboard repository: {exc}"}), 500
