"""Repository modules for all entities."""

from database.repositories.attempt import (
    create_attempt,
    get_attempt,
    list_attempts,
    set_attempt_status,
    update_attempt,
)
from database.repositories.friction import (
    count_friction_by,
    create_friction_log,
    list_friction_logs,
)
from database.repositories.idea import (
    approve_idea,
    create_idea,
    delete_idea,
    find_idea_by_key,
    get_idea,
    list_ideas,
    set_idea_status,
    update_idea,
)
from database.repositories.meeting import (
    create_meeting,
    delete_meeting,
    get_meeting,
    list_meetings,
    set_meeting_ideas_error,
    set_meeting_ideas_state,
    set_meeting_status,
    update_meeting,
)
from database.repositories.repository import (
    catalog_is_current,
    create_repository,
    get_or_create_repository,
    get_repository,
    get_repository_by_source,
    list_repositories,
    save_catalog,
    set_repository_status,
    update_repository,
)

__all__ = [
    # Repository
    "catalog_is_current",
    "create_repository",
    "get_or_create_repository",
    "get_repository",
    "get_repository_by_source",
    "list_repositories",
    "save_catalog",
    "set_repository_status",
    "update_repository",
    # Meeting
    "create_meeting",
    "delete_meeting",
    "get_meeting",
    "list_meetings",
    "set_meeting_ideas_error",
    "set_meeting_ideas_state",
    "set_meeting_status",
    "update_meeting",
    # Idea
    "approve_idea",
    "create_idea",
    "delete_idea",
    "find_idea_by_key",
    "get_idea",
    "list_ideas",
    "set_idea_status",
    "update_idea",
    # Attempt
    "create_attempt",
    "get_attempt",
    "list_attempts",
    "set_attempt_status",
    "update_attempt",
    # Friction
    "count_friction_by",
    "create_friction_log",
    "list_friction_logs",
]
