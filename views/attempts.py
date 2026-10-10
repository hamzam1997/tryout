"""Attempt report: everything one prototype attempt produced, in one payload."""

from __future__ import annotations

from flask import Blueprint, jsonify

import database as db

bp = Blueprint("attempts", __name__, url_prefix="/attempts")


@bp.get("/<int:attempt_id>")
def get_attempt(attempt_id: int):
    attempt = db.get_attempt(attempt_id)
    if attempt is None:
        return jsonify({"error": "attempt not found"}), 404
    idea = db.get_idea(attempt.idea_id)
    payload = attempt.model_dump(mode="json")
    payload["idea_title"] = idea.title if idea else ""
    payload["friction"] = [
        log.model_dump(mode="json") for log in db.list_friction_logs(attempt_id=attempt_id)
    ]
    return jsonify(payload)
