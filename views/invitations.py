"""Invite people to a workspace by email, and accept an invite link."""

from __future__ import annotations

from flask import Blueprint, jsonify, request, session

import database as db
from database.documents import utc_now
from schemas import WorkspaceRole
from views.workspaces import member_with_role

bp = Blueprint("invitations", __name__, url_prefix="/api")

_MANAGERS = (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)


def _public(invitation, workspace=None) -> dict:
    return {
        "token": invitation.token,
        "email": invitation.email,
        "role": invitation.role.value,
        "expires_at": invitation.expires_at.isoformat(),
        **({"workspace": {"id": workspace.id, "name": workspace.name}} if workspace else {}),
    }


@bp.post("/workspaces/<int:workspace_id>/invitations")
def invite(workspace_id: int):
    _, error = member_with_role(workspace_id, *_MANAGERS)
    if error:
        return error
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip()
    if "@" not in email:
        return jsonify({"error": "Enter the email address to invite."}), 400
    try:
        role = WorkspaceRole(body.get("role") or "member")
    except ValueError:
        return jsonify({"error": "Role must be member or admin."}), 400
    if role == WorkspaceRole.OWNER:
        return jsonify({"error": "Role must be member or admin."}), 400
    invitation = db.create_invitation(workspace_id, email, role, session["user"]["uid"])
    return jsonify(_public(invitation)), 201


@bp.get("/workspaces/<int:workspace_id>/invitations")
def list_invitations(workspace_id: int):
    _, error = member_with_role(workspace_id, *_MANAGERS)
    if error:
        return error
    return jsonify([_public(i) for i in db.list_open_invitations(workspace_id)])


@bp.delete("/workspaces/<int:workspace_id>/invitations/<token>")
def revoke(workspace_id: int, token: str):
    _, error = member_with_role(workspace_id, *_MANAGERS)
    if error:
        return error
    invitation = db.get_invitation(token)
    if invitation is None or invitation.workspace_id != workspace_id:
        return jsonify({"error": "invitation not found"}), 404
    invitation.revoked = True
    db.save_invitation(invitation)
    return "", 204


def _usable(token: str):
    """(invitation, None) if the signed-in user may accept it, else (None, error)."""
    invitation = db.get_invitation(token)
    if invitation is None or not invitation.is_open(utc_now()):
        return None, (jsonify({"error": "This invitation is invalid, used or expired."}), 404)
    user = session["user"]
    if (user.get("email") or "").lower() != invitation.email:
        return None, (jsonify({"error": f"This invitation is for {invitation.email}. Sign in with that account."}), 403)
    if not user.get("email_verified"):
        return None, (jsonify({"error": "Verify your email address before accepting."}), 403)
    return invitation, None


@bp.get("/invitations/<token>")
def preview(token: str):
    invitation, error = _usable(token)
    if error:
        return error
    return jsonify(_public(invitation, db.get_workspace(invitation.workspace_id)))


@bp.post("/invitations/<token>/accept")
def accept(token: str):
    invitation, error = _usable(token)
    if error:
        return error
    uid = session["user"]["uid"]
    if db.get_membership(invitation.workspace_id, uid) is None:
        db.add_member(invitation.workspace_id, uid, invitation.role)
    invitation.accepted_at = utc_now()
    db.save_invitation(invitation)
    session["workspace_id"] = invitation.workspace_id
    return jsonify({"workspace_id": invitation.workspace_id})
