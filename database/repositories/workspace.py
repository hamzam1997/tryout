"""Workspaces and their memberships."""

from __future__ import annotations

from database.client import get_firestore_client, get_next_id
from database.documents import utc_now
from schemas import Membership, Workspace, WorkspaceRole

WORKSPACES = "workspaces"
MEMBERSHIPS = "memberships"


def _membership_id(workspace_id: int, uid: str) -> str:
    return f"{workspace_id}_{uid}"


def create_workspace(name: str, owner_uid: str) -> Workspace:
    workspace = Workspace(id=get_next_id(WORKSPACES), name=name, created_by=owner_uid, created_at=utc_now())
    get_firestore_client().collection(WORKSPACES).document(str(workspace.id)).set(
        workspace.model_dump(mode="json")
    )
    add_member(workspace.id, owner_uid, WorkspaceRole.OWNER)
    return workspace


def get_workspace(workspace_id: int) -> Workspace | None:
    snap = get_firestore_client().collection(WORKSPACES).document(str(workspace_id)).get()
    return Workspace.model_validate(snap.to_dict()) if snap.exists else None


def add_member(workspace_id: int, uid: str, role: WorkspaceRole) -> Membership:
    membership = Membership(workspace_id=workspace_id, uid=uid, role=role, created_at=utc_now())
    get_firestore_client().collection(MEMBERSHIPS).document(_membership_id(workspace_id, uid)).set(
        membership.model_dump(mode="json")
    )
    return membership


def get_membership(workspace_id: int, uid: str) -> Membership | None:
    snap = get_firestore_client().collection(MEMBERSHIPS).document(_membership_id(workspace_id, uid)).get()
    return Membership.model_validate(snap.to_dict()) if snap.exists else None


def list_memberships(*, uid: str | None = None, workspace_id: int | None = None) -> list[Membership]:
    query = get_firestore_client().collection(MEMBERSHIPS)
    if uid is not None:
        query = query.where("uid", "==", uid)
    if workspace_id is not None:
        query = query.where("workspace_id", "==", workspace_id)
    memberships = [Membership.model_validate(d.to_dict()) for d in query.stream()]
    return sorted(memberships, key=lambda m: m.workspace_id)


def rename_workspace(workspace_id: int, name: str) -> None:
    get_firestore_client().collection(WORKSPACES).document(str(workspace_id)).set({"name": name}, merge=True)


# Collections whose documents carry a workspace_id (see database/scope.py).
SCOPED_COLLECTIONS = ("repositories", "meetings", "ideas", "attempts", "friction_logs")


def delete_workspace(workspace_id: int) -> None:
    """Delete a workspace with all its records and memberships."""
    client = get_firestore_client()
    for collection in (*SCOPED_COLLECTIONS, MEMBERSHIPS):
        for doc in client.collection(collection).where("workspace_id", "==", workspace_id).stream():
            client.collection(collection).document(doc.id).delete()
    client.collection(WORKSPACES).document(str(workspace_id)).delete()
