"""Firestore repository for User persistence."""

from __future__ import annotations

import logging
from typing import Any

from database.client import get_firestore_client
from database.documents import UserDoc, utc_now
import schemas

logger = logging.getLogger(__name__)


def upsert_user(
    uid: str,
    email: str | None = None,
    name: str | None = None,
    avatar_url: str | None = None,
    provider: str | None = None,
    github_login: str | None = None,
) -> schemas.User:
    """Create or update user details in Firestore `/users/{uid}`."""
    client = get_firestore_client()
    doc_ref = client.collection(UserDoc.COLLECTION).document(str(uid))
    snapshot = doc_ref.get()

    now_iso = utc_now().isoformat()
    if snapshot.exists:
        existing_data = snapshot.to_dict() or {}
        # Merge updates while preserving original created_at
        updated_data: dict[str, Any] = {
            "uid": uid,
            "email": email if email is not None else existing_data.get("email"),
            "name": name if name is not None else existing_data.get("name"),
            "avatar_url": avatar_url if avatar_url is not None else existing_data.get("avatar_url"),
            "provider": provider if provider is not None else existing_data.get("provider"),
            "github_login": github_login if github_login is not None else existing_data.get("github_login"),
            "created_at": existing_data.get("created_at", now_iso),
            "last_login_at": now_iso,
        }
        doc_ref.set(updated_data, merge=True)
        return UserDoc.from_doc(updated_data).to_domain()
    else:
        new_doc = UserDoc(
            uid=uid,
            email=email,
            name=name,
            avatar_url=avatar_url,
            provider=provider,
            github_login=github_login,
            created_at=now_iso,
            last_login_at=now_iso,
        )
        doc_ref.set(new_doc.to_doc())
        return new_doc.to_domain()


def get_user(uid: str) -> schemas.User | None:
    """Retrieve user details by UID."""
    client = get_firestore_client()
    snapshot = client.collection(UserDoc.COLLECTION).document(str(uid)).get()
    if not snapshot.exists:
        return None
    return UserDoc.from_doc(snapshot.to_dict() or {}).to_domain()


def list_users() -> list[schemas.User]:
    """List all registered users."""
    client = get_firestore_client()
    docs = client.collection(UserDoc.COLLECTION).stream()
    users = []
    for d in docs:
        data = d.to_dict()
        if data:
            users.append(UserDoc.from_doc(data).to_domain())
    return users
