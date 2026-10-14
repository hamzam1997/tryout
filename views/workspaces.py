"""List, create, switch, rename and delete the signed-in user's workspaces."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request, session

import database as db
from schemas import WorkspaceRole

bp = Blueprint("workspaces", __name__, url_prefix="/api/workspaces")


def _uid() -> str:
    return session["user"]["uid"]


def _name_from_body() -> str | None:
    name = ((request.get_json(silent=True) or {}).get("name") or "").strip()
    return name[:80] or None


def _owned(workspace_id: int):
    """The workspace if the user owns it, else an error response."""
    membership = db.get_membership(workspace_id, _uid())
    if membership is None:
        return None, (jsonify({"error": "workspace not found"}), 404)
    if membership.role != WorkspaceRole.OWNER:
        return None, (jsonify({"error": "Only the workspace owner can do that."}), 403)
    return db.get_workspace(workspace_id), None


@bp.get("")
def list_workspaces():
    items = []
    for membership in db.list_memberships(uid=_uid()):
        workspace = db.get_workspace(membership.workspace_id)
        if workspace:
            items.append({"id": workspace.id, "name": workspace.name, "role": membership.role.value})
    return jsonify({"current": g.membership.workspace_id, "workspaces": items})


@bp.post("")
def create_workspace():
    name = _name_from_body()
    if not name:
        return jsonify({"error": "Give the workspace a name."}), 400
    workspace = db.create_workspace(name, _uid())
    session["workspace_id"] = workspace.id
    return jsonify({"id": workspace.id, "name": workspace.name, "role": "owner"}), 201


@bp.post("/<int:workspace_id>/switch")
def switch_workspace(workspace_id: int):
    if db.get_membership(workspace_id, _uid()) is None:
        return jsonify({"error": "workspace not found"}), 404
    session["workspace_id"] = workspace_id
    return jsonify({"current": workspace_id})


@bp.patch("/<int:workspace_id>")
def rename_workspace(workspace_id: int):
    workspace, error = _owned(workspace_id)
    if error:
        return error
    name = _name_from_body()
    if not name:
        return jsonify({"error": "Give the workspace a name."}), 400
    db.rename_workspace(workspace_id, name)
    return jsonify({"id": workspace.id, "name": name})


@bp.delete("/<int:workspace_id>")
def delete_workspace(workspace_id: int):
    _, error = _owned(workspace_id)
    if error:
        return error
    db.delete_workspace(workspace_id)
    session.pop("workspace_id", None)  # the next request falls back to another workspace
    return "", 204
