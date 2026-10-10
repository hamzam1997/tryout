"""Attempt report and live progress stream."""

from __future__ import annotations

import json
import time

from flask import Blueprint, Response, jsonify, request, stream_with_context

import database as db
from schemas import AttemptStatus

bp = Blueprint("attempts", __name__, url_prefix="/attempts")

_FINISHED = {AttemptStatus.COMPLETE, AttemptStatus.FAILED, AttemptStatus.READY_FOR_REVIEW}
_POLL_SECONDS = 0.5
# Below Cloud Run's request timeout; EventSource reconnects and resumes via Last-Event-ID.
_STREAM_SECONDS = 240


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


def _sse(event: str, data, event_id: int | None = None) -> str:
    head = f"id: {event_id}\n" if event_id is not None else ""
    return f"{head}event: {event}\ndata: {json.dumps(data)}\n\n"


@bp.get("/<int:attempt_id>/stream")
def stream_attempt(attempt_id: int):
    """Server-sent events: one `step` per harness event, `status` changes, then `done`.

    Reads the attempt from the database rather than an in-process queue, so it works
    no matter which instance runs the attempt.
    """
    # ponytail: DB polling (2 reads/s per viewer); push via Firestore listeners if viewers grow.
    if db.get_attempt(attempt_id) is None:
        return jsonify({"error": "attempt not found"}), 404
    sent = int(request.headers.get("Last-Event-ID", 0) or 0)

    def events():
        nonlocal sent
        status = None
        deadline = time.monotonic() + _STREAM_SECONDS
        while time.monotonic() < deadline:
            attempt = db.get_attempt(attempt_id)
            if attempt is None:
                return
            if attempt.status != status:
                status = attempt.status
                yield _sse("status", {"status": status.value})
            for step in attempt.events[sent:]:
                sent += 1
                yield _sse("step", step.model_dump(mode="json"), event_id=sent)
            if status in _FINISHED:
                yield _sse("done", {"status": status.value})
                return
            # A comment line each tick: a closed client fails the write and ends the generator.
            yield ": tick\n\n"
            time.sleep(_POLL_SECONDS)

    return Response(
        stream_with_context(events()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
