"""Workspaces and their memberships."""

from __future__ import annotations

from database.client import get_firestore_client, get_next_id
from database.documents import MembershipDoc, WorkspaceDoc, utc_now
from schemas import Membership, Workspace, WorkspaceRole


def create_workspace(name: str, owner_uid: str) -> Workspace:
    workspace = Workspace(id=get_next_id(WorkspaceDoc.COLLECTION), name=name, created_by=owner_uid, created_at=utc_now())
    doc = WorkspaceDoc.from_domain(workspace)
    get_firestore_client().collection(WorkspaceDoc.COLLECTION).document(str(doc.id)).set(doc.to_doc())
    add_member(workspace.id, owner_uid, WorkspaceRole.OWNER)
    return workspace


def get_workspace(workspace_id: int) -> Workspace | None:
    snap = get_firestore_client().collection(WorkspaceDoc.COLLECTION).document(str(workspace_id)).get()
    return WorkspaceDoc.from_doc(snap.to_dict()).to_domain() if snap.exists else None


def add_member(workspace_id: int, uid: str, role: WorkspaceRole) -> Membership:
    membership = Membership(workspace_id=workspace_id, uid=uid, role=role, created_at=utc_now())
    doc = MembershipDoc.from_domain(membership)
    get_firestore_client().collection(MembershipDoc.COLLECTION).document(doc.doc_id).set(doc.to_doc())
    return membership


def get_membership(workspace_id: int, uid: str) -> Membership | None:
    doc_id = MembershipDoc(workspace_id=workspace_id, uid=uid).doc_id
    snap = get_firestore_client().collection(MembershipDoc.COLLECTION).document(doc_id).get()
    return MembershipDoc.from_doc(snap.to_dict()).to_domain() if snap.exists else None


def list_memberships(*, uid: str | None = None, workspace_id: int | None = None) -> list[Membership]:
    query = get_firestore_client().collection(MembershipDoc.COLLECTION)
    if uid is not None:
        query = query.where("uid", "==", uid)
    if workspace_id is not None:
        query = query.where("workspace_id", "==", workspace_id)
    memberships = [MembershipDoc.from_doc(d.to_dict()).to_domain() for d in query.stream()]
    return sorted(memberships, key=lambda m: m.workspace_id)
