"""The workspace the current request or background job works in.

Set once per request (`views/auth.py`) and carried into background threads with
`contextvars.copy_context()`. Every repository function goes through these helpers,
so records never leak across workspaces. With no workspace set (CLI scripts,
migrations) queries are unscoped.
"""

from __future__ import annotations

from contextvars import ContextVar

_current: ContextVar[int | None] = ContextVar("workspace_id", default=None)


def set_workspace(workspace_id: int | None) -> None:
    _current.set(workspace_id)


def current_workspace() -> int | None:
    return _current.get()


def scoped(query):
    """Restrict a collection or query to the current workspace."""
    workspace_id = _current.get()
    return query if workspace_id is None else query.where("workspace_id", "==", workspace_id)


def exists(snapshot) -> bool:
    """A fetched document exists and belongs to the current workspace."""
    if not snapshot.exists:
        return False
    workspace_id = _current.get()
    return workspace_id is None or (snapshot.to_dict() or {}).get("workspace_id") == workspace_id


def stamped(data: dict) -> dict:
    """Tag a new document with the current workspace."""
    workspace_id = _current.get()
    if workspace_id is not None:
        data["workspace_id"] = workspace_id
    return data
