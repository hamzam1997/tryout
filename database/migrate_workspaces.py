"""One-time migration: move records created before workspaces into one workspace.

    python -m database.migrate_workspaces you@example.com ["Workspace name"]

The user (by email) must have signed in once. Records that already have a
workspace are left alone, so running it twice is safe.
"""

from __future__ import annotations

import sys

import database as db
from database.client import get_firestore_client

COLLECTIONS = ("repositories", "meetings", "ideas", "attempts", "friction_logs")


def migrate(owner_email: str, name: str = "Default") -> tuple[int, int]:
    """Returns (workspace id, number of records moved)."""
    owner = next((u for u in db.list_users() if u.email == owner_email), None)
    if owner is None:
        raise SystemExit(f"No signed-in user with email {owner_email}; sign in once first.")
    workspace = db.create_workspace(name, owner.uid)
    client = get_firestore_client()
    moved = 0
    for collection in COLLECTIONS:
        for doc in client.collection(collection).stream():
            if (doc.to_dict() or {}).get("workspace_id") is None:
                client.collection(collection).document(doc.id).set({"workspace_id": workspace.id}, merge=True)
                moved += 1
    return workspace.id, moved


if __name__ == "__main__":
    db.init_db()
    workspace_id, moved = migrate(sys.argv[1], *sys.argv[2:3])
    print(f"Moved {moved} record(s) into workspace {workspace_id}.")
