"""Idea inbox endpoints: list, inspect, approve, reject.

Approval is the human gate before any attempt/planning work starts.
Reject keeps the idea for audit without queuing an attempt.
"""

from __future__ import annotations

import functools

from flask import Blueprint, jsonify, request, session

import database as db
from agents.attempt_jobs import queue_attempt
from views.workspaces import request_github_token
from schemas import Attempt, AttemptStatus, IdeaStatus

bp = Blueprint("ideas", __name__, url_prefix="/api/ideas")

_VALID_STATUSES = {status.value for status in IdeaStatus}
_DEFAULT_APPROVER = "local"


def _serialise(idea) -> dict:
    payload = idea.model_dump(mode="json")
    meeting = db.get_meeting(idea.meeting_id)
    payload["meeting_title"] = meeting.title if meeting else ""
    payload["attempts"] = [_serialise_attempt(item) for item in db.list_attempts(idea_id=idea.id)]
    return payload


def _serialise_attempt(attempt) -> dict:
    return attempt.model_dump(mode="json")


def _latest_attempt_payload(attempt) -> dict | None:
    if attempt is None:
        return None
    return {
        "id": attempt.id,
        "repository_id": attempt.repository_id,
        "repo_ref": attempt.repo_ref,
        "base_branch": attempt.base_branch,
        "branch_name": attempt.branch_name,
        "pull_request_url": attempt.pull_request_url,
        "status": attempt.status.value,
        "error": attempt.error,
    }


def _serialise_summary(idea, latest_attempt=None) -> dict:
    meeting = db.get_meeting(idea.meeting_id)
    return {
        "id": idea.id,
        "meeting_id": idea.meeting_id,
        "repository_id": idea.repository_id,
        "meeting_title": meeting.title if meeting else "",
        "title": idea.title,
        "speaker": idea.speaker,
        "priority": idea.priority,
        "status": idea.status.value,
        "approved_by": idea.approved_by,
        "created_at": idea.created_at.isoformat() if idea.created_at else None,
        "original_idea_id": idea.original_idea_id,
        "catalog_refs": idea.catalog_refs or [],
        "latest_attempt": _latest_attempt_payload(latest_attempt),
    }


def _approved_by_from_request() -> str:
    user = session.get("user") or session.get("github_user")
    if user:
        return (user.get("name") or user.get("login") or "").strip() or _DEFAULT_APPROVER
    return _DEFAULT_APPROVER


@bp.get("/counts")
def get_idea_counts():
    """Return status counts across all ideas."""
    return jsonify(db.get_idea_counts())


@bp.get("")
def list_ideas():
    status_param = (request.args.get("status") or "").strip().upper()
    status = None
    if status_param and status_param != "ALL":
        if status_param not in _VALID_STATUSES:
            return jsonify(
                {"error": f"status must be one of {sorted(_VALID_STATUSES)}"}
            ), 400
        status = IdeaStatus(status_param)

    meeting_id = request.args.get("meeting_id", type=int)
    ideas = db.list_ideas(status=status, meeting_id=meeting_id)
    latest_attempts = {}
    for attempt in db.list_attempts():
        latest_attempts.setdefault(attempt.idea_id, attempt)
    return jsonify(
        [_serialise_summary(idea, latest_attempts.get(idea.id)) for idea in ideas]
    )


@bp.get("/<int:idea_id>")
def get_idea(idea_id: int):
    idea = db.get_idea(idea_id)
    if idea is None:
        return jsonify({"error": "idea not found"}), 404
    return jsonify(_serialise(idea))


def _one_at_a_time(view):
    """Serialise attempt-starting requests per idea: a double click or two members
    approving at once would otherwise both pass the status check and open two PRs."""

    @functools.wraps(view)
    def wrapper(idea_id: int):
        lock = f"idea-attempt:{idea_id}"
        if not db.claim(lock):
            return jsonify({"error": "This idea is already being started."}), 409
        try:
            return view(idea_id)
        finally:
            db.release(lock)

    return wrapper


@bp.post("/<int:idea_id>/approve")
@_one_at_a_time
def approve_idea_endpoint(idea_id: int):
    """Approve an idea, persist an attempt, and start background planning."""
    idea = db.get_idea(idea_id)
    if idea is None:
        return jsonify({"error": "idea not found"}), 404
    if idea.status != IdeaStatus.PENDING:
        return jsonify(
            {"error": f"only PENDING ideas can be approved (current: {idea.status.value})"}
        ), 409

    body = request.get_json(silent=True) or {}
    repository_id = body.get("repository_id", idea.repository_id)
    if not isinstance(repository_id, int):
        return jsonify({"error": "Choose a repository before approving this idea."}), 400
    repository = db.get_repository(repository_id)
    if repository is None:
        return jsonify({"error": "Repository not found."}), 404
    if repository.catalog_status != "ready" or repository.catalog is None:
        return jsonify({"error": "The selected repository needs a ready architecture catalog."}), 409

    in_process = db.approve_idea(idea_id, _approved_by_from_request())
    try:
        attempt = db.create_attempt(
            Attempt(
                idea_id=idea_id,
                repository_id=repository_id,
                repo_ref=repository.source_ref,
                status=AttemptStatus.QUEUED,
            )
        )
    except Exception:
        db.set_idea_status(idea_id, IdeaStatus.PENDING)
        raise

    try:
        queue_attempt(attempt.id, request_github_token())
    except Exception as exc:
        db.set_attempt_status(attempt.id, AttemptStatus.FAILED, error=str(exc))

    response = _serialise(in_process)
    response["latest_attempt"] = _serialise_attempt(db.get_attempt(attempt.id) or attempt)
    return jsonify(response), 202


@bp.post("/<int:idea_id>/attempts/retry")
@_one_at_a_time
def retry_attempt_endpoint(idea_id: int):
    """Start a fresh attempt after a previous generation or PR failed."""
    idea = db.get_idea(idea_id)
    if idea is None:
        return jsonify({"error": "idea not found"}), 404
    if idea.status not in (IdeaStatus.IN_PROCESS, IdeaStatus.DONE):
        return jsonify({"error": "only approved ideas can retry an attempt"}), 409

    attempts = db.list_attempts(idea_id=idea_id)
    latest = attempts[0] if attempts else None
    if latest is None:
        return jsonify({"error": "there is no previous attempt to retry"}), 409
    if latest.status not in (AttemptStatus.FAILED, AttemptStatus.READY_FOR_REVIEW):
        return jsonify({"error": "the latest attempt is still running"}), 409
    if latest.pull_request_url:
        return jsonify({"error": "the latest attempt already has a pull request"}), 409

    repository = db.get_repository(latest.repository_id)
    if repository is None or repository.catalog_status != "ready" or repository.catalog is None:
        return jsonify({"error": "the attempt repository needs a ready architecture catalog"}), 409

    attempt = db.create_attempt(
        Attempt(
            idea_id=idea_id,
            repository_id=repository.id,
            repo_ref=repository.source_ref,
            status=AttemptStatus.QUEUED,
        )
    )
    if idea.status == IdeaStatus.DONE:
        idea.status = IdeaStatus.IN_PROCESS
        db.update_idea(idea)
    try:
        queue_attempt(attempt.id, request_github_token())
    except Exception as exc:
        db.set_attempt_status(attempt.id, AttemptStatus.FAILED, error=str(exc))

    response = _serialise(db.get_idea(idea_id))
    response["latest_attempt"] = _serialise_attempt(db.get_attempt(attempt.id) or attempt)
    return jsonify(response), 202


@bp.post("/<int:idea_id>/reject")
@_one_at_a_time
def reject_idea(idea_id: int):
    idea = db.get_idea(idea_id)
    if idea is None:
        return jsonify({"error": "idea not found"}), 404
    if idea.status != IdeaStatus.PENDING:
        return jsonify(
            {"error": f"only PENDING ideas can be rejected (current: {idea.status.value})"}
        ), 409

    db.set_idea_status(idea_id, IdeaStatus.REJECTED)
    return jsonify(_serialise(db.get_idea(idea_id)))


@bp.delete("/<int:idea_id>")
def delete_idea(idea_id: int):
    """Delete an idea and its cascaded attempts."""
    if not db.delete_idea(idea_id):
        return jsonify({"error": "idea not found"}), 404
    return "", 204
