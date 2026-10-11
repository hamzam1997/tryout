"""Database package using Google Cloud Firestore."""

from __future__ import annotations

import logging
from database.scope import current_workspace, set_workspace
from database.client import (
    force_in_memory_firestore,
    get_firestore_client,
    reset_in_memory_firestore,
)
from database.documents import (
    AttemptDoc,
    FrictionLogDoc,
    IdeaDoc,
    MeetingDoc,
    RepositoryDoc,
    UserDoc,
    utc_now,
)
from database.repositories import (
    add_member,
    create_workspace,
    delete_workspace,
    get_membership,
    get_workspace,
    list_memberships,
    rename_workspace,
    approve_idea,
    catalog_is_current,
    count_friction_by,
    create_attempt,
    create_friction_log,
    create_idea,
    create_meeting,
    create_repository,
    delete_idea,
    delete_meeting,
    delete_repository,
    find_idea_by_key,
    find_meeting_by_external_id,
    find_meeting_by_transcript,
    get_attempt,
    get_idea,
    get_idea_counts,
    get_meeting,
    get_or_create_repository,
    get_repository,
    get_repository_by_source,
    get_user,
    list_attempts,
    list_friction_logs,
    list_ideas,
    list_meetings,
    list_repositories,
    list_users,
    save_catalog,
    set_attempt_status,
    set_idea_status,
    set_meeting_ideas_error,
    set_meeting_ideas_state,
    set_meeting_status,
    set_repository_status,
    update_attempt,
    update_idea,
    update_meeting,
    update_repository,
    upsert_user,
)
from schemas import (
    ArchitectureCatalog,
    Attempt,
    AttemptStatus,
    FileRole,
    FrictionCategory,
    FrictionLog,
    Idea,
    IdeasExtractStatus,
    IdeaStatus,
    IntegrationEntry,
    Meeting,
    MeetingMinutes,
    MeetingSource,
    MeetingStatus,
    ModelEntry,
    ModuleDescription,
    PlanStep,
    ReadinessItem,
    RepoSource,
    Repository,
    RouteEntry,
    TechnicalPlan,
)

logger = logging.getLogger(__name__)


class IntegrityError(Exception):
    """Integrity violation error (e.g. duplicate key or missing foreign entity)."""
    pass


def init_db() -> None:
    """Initialize database connection. Verifies Firestore connectivity."""
    try:
        client = get_firestore_client()
        logger.info("Firestore database initialized successfully.")
    except Exception as exc:
        logger.warning("Firestore client initialization deferred: %s", exc)


def set_database_path(path=None) -> None:
    """Test compatibility hook for isolation in tests."""
    set_workspace(None)  # a fresh database has no workspaces to be scoped to
    reset_in_memory_firestore()
    if path is not None:
        force_in_memory_firestore(True)
    else:
        force_in_memory_firestore(False)


__all__ = [
    "add_member",
    "create_workspace",
    "delete_workspace",
    "current_workspace",
    "get_membership",
    "get_workspace",
    "list_memberships",
    "rename_workspace",
    "set_workspace",
    "init_db",
    "set_database_path",
    "get_firestore_client",
    "force_in_memory_firestore",
    "reset_in_memory_firestore",
    "utc_now",
    "IntegrityError",
    # Document models
    "RepositoryDoc",
    "MeetingDoc",
    "IdeaDoc",
    "AttemptDoc",
    "FrictionLogDoc",
    "UserDoc",
    # Domain schemas
    "ArchitectureCatalog",
    "Attempt",
    "AttemptStatus",
    "FrictionCategory",
    "FrictionLog",
    "Idea",
    "IdeasExtractStatus",
    "IdeaStatus",
    "Meeting",
    "MeetingMinutes",
    "MeetingSource",
    "MeetingStatus",
    "ReadinessItem",
    "RepoSource",
    "Repository",
    "TechnicalPlan",
    "User",
    # Repositories
    "approve_idea",
    "catalog_is_current",
    "count_friction_by",
    "create_attempt",
    "create_friction_log",
    "create_idea",
    "create_meeting",
    "create_repository",
    "delete_idea",
    "delete_meeting",
    "delete_repository",
    "find_idea_by_key",
    "find_meeting_by_external_id",
    "find_meeting_by_transcript",
    "get_attempt",
    "get_idea",
    "get_idea_counts",
    "get_meeting",
    "get_or_create_repository",
    "get_repository",
    "get_repository_by_source",
    "get_user",
    "list_attempts",
    "list_friction_logs",
    "list_ideas",
    "list_meetings",
    "list_repositories",
    "list_users",
    "save_catalog",
    "set_attempt_status",
    "set_idea_status",
    "set_meeting_ideas_error",
    "set_meeting_ideas_state",
    "set_meeting_status",
    "set_repository_status",
    "update_attempt",
    "update_idea",
    "update_meeting",
    "update_repository",
    "upsert_user",
]
