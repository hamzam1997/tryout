"""Idea inbox endpoints: list, inspect, approve, reject.

Approval is the human gate before any attempt/planning work starts.
Reject keeps the idea for audit without queuing an attempt.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request, session

import database as db
from agents.attempt_jobs import queue_attempt
from schemas import Attempt, AttemptStatus, IdeaStatus

bp = Blueprint("ideas", __name__, url_prefix="/ideas")

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


@bp.post("/<int:idea_id>/approve")
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
        queue_attempt(attempt.id, session.get("github_token"))
    except Exception as exc:
        db.set_attempt_status(attempt.id, AttemptStatus.FAILED, error=str(exc))

    response = _serialise(in_process)
    response["latest_attempt"] = _serialise_attempt(db.get_attempt(attempt.id) or attempt)
    return jsonify(response), 202


@bp.post("/<int:idea_id>/reject")
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
