"""Workspaces and their memberships."""

from __future__ import annotations

from database.client import get_firestore_client, get_next_id
import secrets
from datetime import timedelta

from database.documents import InvitationDoc, MembershipDoc, WorkspaceDoc, utc_now
from schemas import Invitation, Membership, Workspace, WorkspaceRole

INVITE_TTL = timedelta(days=7)


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


def set_member_role(workspace_id: int, uid: str, role: WorkspaceRole) -> None:
    doc_id = MembershipDoc(workspace_id=workspace_id, uid=uid).doc_id
    get_firestore_client().collection(MembershipDoc.COLLECTION).document(doc_id).set({"role": role.value}, merge=True)


def remove_member(workspace_id: int, uid: str) -> None:
    doc_id = MembershipDoc(workspace_id=workspace_id, uid=uid).doc_id
    get_firestore_client().collection(MembershipDoc.COLLECTION).document(doc_id).delete()


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


def rename_workspace(workspace_id: int, name: str) -> None:
    get_firestore_client().collection(WorkspaceDoc.COLLECTION).document(str(workspace_id)).set({"name": name}, merge=True)


# Collections whose documents carry a workspace_id (see database/scope.py).
SCOPED_COLLECTIONS = ("repositories", "meetings", "ideas", "attempts", "friction_logs")


def delete_workspace(workspace_id: int) -> None:
    """Delete a workspace with all its records and memberships."""
    client = get_firestore_client()
    for collection in (*SCOPED_COLLECTIONS, MembershipDoc.COLLECTION, InvitationDoc.COLLECTION):
        for doc in client.collection(collection).where("workspace_id", "==", workspace_id).stream():
            client.collection(collection).document(doc.id).delete()
    client.collection(WorkspaceDoc.COLLECTION).document(str(workspace_id)).delete()


def create_invitation(workspace_id: int, email: str, role: WorkspaceRole, invited_by: str) -> Invitation:
    now = utc_now()
    invitation = Invitation(
        token=secrets.token_urlsafe(24),
        workspace_id=workspace_id,
        email=email.strip().lower(),
        role=role,
        invited_by=invited_by,
        created_at=now,
        expires_at=now + INVITE_TTL,
    )
    save_invitation(invitation)
    return invitation


def save_invitation(invitation: Invitation) -> None:
    doc = InvitationDoc.from_domain(invitation)
    get_firestore_client().collection(InvitationDoc.COLLECTION).document(doc.token).set(doc.to_doc())


def get_invitation(token: str) -> Invitation | None:
    snap = get_firestore_client().collection(InvitationDoc.COLLECTION).document(token).get()
    return InvitationDoc.from_doc(snap.to_dict()).to_domain() if snap.exists else None


def list_open_invitations(workspace_id: int) -> list[Invitation]:
    now = utc_now()
    docs = get_firestore_client().collection(InvitationDoc.COLLECTION).where("workspace_id", "==", workspace_id).stream()
    invitations = [InvitationDoc.from_doc(d.to_dict()).to_domain() for d in docs]
    return sorted((i for i in invitations if i.is_open(now)), key=lambda i: i.created_at)
