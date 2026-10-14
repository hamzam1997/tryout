"""Restrict repository reads and writes to the current workspace (see `context.py`).

Every repository function goes through these helpers, so records never leak across
workspaces. With no workspace set (CLI scripts, migrations) queries are unscoped.
"""

from __future__ import annotations

from context import current_workspace


def scoped(query):
    """Restrict a collection or query to the current workspace."""
    workspace_id = current_workspace()
    return query if workspace_id is None else query.where("workspace_id", "==", workspace_id)


def exists(snapshot) -> bool:
    """A fetched document exists and belongs to the current workspace."""
    if not snapshot.exists:
        return False
    workspace_id = current_workspace()
    return workspace_id is None or (snapshot.to_dict() or {}).get("workspace_id") == workspace_id

