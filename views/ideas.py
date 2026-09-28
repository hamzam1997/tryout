"""Idea inbox endpoints: list, inspect, approve, reject.

Approval is the human gate before any attempt/planning work starts.
Reject keeps the idea for audit without queuing an attempt.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

import database as db
from schemas import IdeaStatus

bp = Blueprint("ideas", __name__, url_prefix="/ideas")

_VALID_STATUSES = {status.value for status in IdeaStatus}
_DEFAULT_APPROVER = "local"


def _serialise(idea) -> dict:
    payload = idea.model_dump(mode="json")
    meeting = db.get_meeting(idea.meeting_id)
    payload["meeting_title"] = meeting.title if meeting else ""
    return payload


def _approved_by_from_request() -> str:
    payload = request.get_json(silent=True) or {}
    if isinstance(payload, dict):
        name = (payload.get("approved_by") or "").strip()
        if name:
            return name
    query_name = (request.args.get("approved_by") or "").strip()
    return query_name or _DEFAULT_APPROVER


@bp.get("")
def list_ideas():
    status_param = (request.args.get("status") or "").strip().upper()
    status = None
    if status_param:
        if status_param not in _VALID_STATUSES:
            return jsonify(
                {"error": f"status must be one of {sorted(_VALID_STATUSES)}"}
            ), 400
        status = IdeaStatus(status_param)

    meeting_id = request.args.get("meeting_id", type=int)
    ideas = db.list_ideas(status=status, meeting_id=meeting_id)
    return jsonify([_serialise(idea) for idea in ideas])


@bp.get("/<int:idea_id>")
def get_idea(idea_id: int):
    idea = db.get_idea(idea_id)
    if idea is None:
        return jsonify({"error": "idea not found"}), 404
    return jsonify(_serialise(idea))


@bp.post("/<int:idea_id>/approve")
def approve_idea_endpoint(idea_id: int):
    """Approve an idea and move it to IN_PROCESS when processing starts."""
    idea = db.get_idea(idea_id)
    if idea is None:
        return jsonify({"error": "idea not found"}), 404
    if idea.status != IdeaStatus.PENDING:
        return jsonify(
            {"error": f"only PENDING ideas can be approved (current: {idea.status.value})"}
        ), 409

    # Approval is the gate; status becomes IN_PROCESS as the attempt pipeline starts.
    in_process = db.approve_idea(idea_id, _approved_by_from_request())
    return jsonify(_serialise(in_process))


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
