"""List, create, switch, rename and delete the signed-in user's workspaces."""

from __future__ import annotations

import requests
from flask import Blueprint, g, jsonify, request, session

import database as db
from schemas import WorkspaceRole

bp = Blueprint("workspaces", __name__, url_prefix="/api/workspaces")


def _uid() -> str:
    return session["user"]["uid"]


def _name_from_body() -> str | None:
    name = ((request.get_json(silent=True) or {}).get("name") or "").strip()
    return name[:80] or None


def member_with_role(workspace_id: int, *roles: WorkspaceRole):
    """(membership, None) if the user holds one of `roles` there, else (None, error response)."""
    membership = db.get_membership(workspace_id, _uid())
    if membership is None:
        return None, (jsonify({"error": "workspace not found"}), 404)
    if membership.role not in roles:
        allowed = " or ".join(r.value for r in roles)
        return None, (jsonify({"error": f"Only a workspace {allowed} can do that."}), 403)
    return membership, None


def _owned(workspace_id: int):
    """The workspace if the user owns it, else an error response."""
    _, error = member_with_role(workspace_id, WorkspaceRole.OWNER)
    return (None, error) if error else (db.get_workspace(workspace_id), None)


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


def _owner_count(workspace_id: int) -> int:
    return sum(m.role == WorkspaceRole.OWNER for m in db.list_memberships(workspace_id=workspace_id))


@bp.get("/<int:workspace_id>/members")
def list_members(workspace_id: int):
    _, error = member_with_role(workspace_id, *WorkspaceRole)
    if error:
        return error
    members = []
    for membership in db.list_memberships(workspace_id=workspace_id):
        user = db.get_user(membership.uid)
        members.append({
            "uid": membership.uid,
            "name": (user.name if user else None) or membership.uid,
            "email": user.email if user else None,
            "role": membership.role.value,
            "joined_at": membership.created_at.isoformat() if membership.created_at else None,
            "you": membership.uid == _uid(),
        })
    return jsonify(members)


@bp.patch("/<int:workspace_id>/members/<uid>")
def change_role(workspace_id: int, uid: str):
    me, error = member_with_role(workspace_id, WorkspaceRole.OWNER, WorkspaceRole.ADMIN)
    if error:
        return error
    target = db.get_membership(workspace_id, uid)
    if target is None:
        return jsonify({"error": "member not found"}), 404
    try:
        role = WorkspaceRole((request.get_json(silent=True) or {}).get("role"))
    except ValueError:
        return jsonify({"error": "Role must be owner, admin or member."}), 400
    if me.role != WorkspaceRole.OWNER and WorkspaceRole.OWNER in (role, target.role):
        return jsonify({"error": "Only an owner can grant or change the owner role."}), 403
    if target.role == WorkspaceRole.OWNER and role != WorkspaceRole.OWNER and _owner_count(workspace_id) == 1:
        return jsonify({"error": "A workspace needs at least one owner."}), 409
    db.set_member_role(workspace_id, uid, role)
    return jsonify({"uid": uid, "role": role.value})


@bp.delete("/<int:workspace_id>/members/<uid>")
def remove_member(workspace_id: int, uid: str):
    """Leave (yourself) or remove someone (admin / owner)."""
    if uid == _uid():
        me, error = member_with_role(workspace_id, *WorkspaceRole)
    else:
        me, error = member_with_role(workspace_id, WorkspaceRole.OWNER, WorkspaceRole.ADMIN)
    if error:
        return error
    target = db.get_membership(workspace_id, uid)
    if target is None:
        return jsonify({"error": "member not found"}), 404
    if target.role == WorkspaceRole.OWNER and me.role != WorkspaceRole.OWNER:
        return jsonify({"error": "Only an owner can remove an owner."}), 403
    if target.role == WorkspaceRole.OWNER and _owner_count(workspace_id) == 1:
        return jsonify({"error": "A workspace needs at least one owner. Delete it or make someone else owner first."}), 409
    db.remove_member(workspace_id, uid)
    if uid == _uid():
        session.pop("workspace_id", None)
    return "", 204


def request_github_token() -> str | None:
    """GitHub credential for work in the current workspace: the workspace connection,
    else the signed-in user's own token."""
    return db.get_github_token(g.membership.workspace_id) or session.get("github_token")


@bp.get("/<int:workspace_id>/github")
def github_connection(workspace_id: int):
    _, error = member_with_role(workspace_id, *WorkspaceRole)
    if error:
        return error
    connection = db.get_github_connection(workspace_id)
    return jsonify({"connected": connection is not None, **(connection or {})})


@bp.post("/<int:workspace_id>/github")
def connect_github(workspace_id: int):
    """Share the caller's GitHub sign-in with the workspace."""
    _, error = member_with_role(workspace_id, WorkspaceRole.OWNER, WorkspaceRole.ADMIN)
    if error:
        return error
    token = session.get("github_token")
    if not token:
        return jsonify({"error": "Sign in with GitHub first, then connect it to the workspace."}), 400
    resp = requests.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {token}", "User-Agent": "tryout-app"},
        timeout=10,
    )
    if resp.status_code != 200:
        return jsonify({"error": "Your GitHub sign-in has expired. Sign in with GitHub again."}), 400
    login = resp.json().get("login") or ""
    db.save_github_connection(workspace_id, token, login, _uid())
    return jsonify({"connected": True, **db.get_github_connection(workspace_id)})


@bp.delete("/<int:workspace_id>/github")
def disconnect_github(workspace_id: int):
    _, error = member_with_role(workspace_id, WorkspaceRole.OWNER, WorkspaceRole.ADMIN)
    if error:
        return error
    db.delete_github_connection(workspace_id)
    return "", 204
