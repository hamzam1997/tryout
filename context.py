"""The workspace the current request or background job works in.

Set once per request (`views/auth.py`) and carried into background threads with
`contextvars.copy_context()`. With no workspace set (CLI scripts, migrations)
`database.scope` leaves queries unscoped.
"""

from __future__ import annotations

from contextvars import ContextVar

_current: ContextVar[int | None] = ContextVar("workspace_id", default=None)


def set_workspace(workspace_id: int | None) -> None:
    _current.set(workspace_id)


def current_workspace() -> int | None:
    return _current.get()
