"""Organization bottleneck map: friction logs aggregated across every attempt."""

from __future__ import annotations

from collections import Counter

from flask import Blueprint, jsonify

import database as db

bp = Blueprint("bottlenecks", __name__, url_prefix="/api/bottlenecks")

# Rough engineering weeks a blocker typically costs when found late (mid-sprint)
# instead of on day 0. An assumption, not a measurement; the UI labels it an estimate.
WEEKS_PER_BLOCKER = {
    "EXTERNAL_SERVICE_DEPENDENCY": 2.0,
    "AUTH_CREDENTIAL_REQUIRED": 1.0,
    "SCHEMA_MIGRATION_REQUIRED": 1.5,
    "CROSS_TEAM_CONTRACT": 2.0,
    "PRODUCT_DECISION": 1.0,
}


def _ranked(counter: Counter) -> list[dict]:
    return [
        {"name": name, "count": count}
        for name, count in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


@bp.get("")
def bottleneck_map():
    logs = db.list_friction_logs()
    titles: dict[int, str] = {}  # attempt_id -> idea title (one lookup per attempt)
    rows = []
    for log in logs:
        if log.attempt_id not in titles:
            attempt = db.get_attempt(log.attempt_id)
            idea = db.get_idea(attempt.idea_id) if attempt else None
            titles[log.attempt_id] = idea.title if idea else ""
        rows.append({
            "id": log.id,
            "attempt_id": log.attempt_id,
            "idea_title": titles[log.attempt_id],
            "category": log.category.value,
            "service_name": log.service_name,
            "owning_team": log.owning_team or "unknown",
            "mock_implementation_path": log.mock_implementation_path,
            "required_action": log.required_action,
            "readiness_checklist": [i.model_dump() for i in log.readiness_checklist],
        })
    rows.sort(key=lambda r: -r["id"])

    return jsonify({
        "total": len(rows),
        "attempts": len(titles),
        "by_category": _ranked(Counter(r["category"] for r in rows)),
        "by_service": _ranked(Counter(r["service_name"] for r in rows if r["service_name"])),
        "by_team": _ranked(Counter(r["owning_team"] for r in rows if r["owning_team"] != "unknown")),
        "weeks_saved": sum(WEEKS_PER_BLOCKER.get(r["category"], 1.0) for r in rows),
        "logs": rows,
    })
