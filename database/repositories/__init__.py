"""Repository modules for all entities."""

from database.repositories.attempt import (
    create_attempt,
    get_attempt,
    list_attempts,
    row_to_attempt,
    set_attempt_status,
    update_attempt,
)
from database.repositories.friction import (
    count_friction_by,
    create_friction_log,
    list_friction_logs,
    row_to_friction_log,
)
from database.repositories.idea import (
    create_idea,
    find_idea_by_fingerprint,
    get_idea,
    list_ideas,
    row_to_idea,
    set_idea_status,
    update_idea,
)
from database.repositories.meeting import (
    create_meeting,
    get_meeting,
    list_meetings,
    row_to_meeting,
    update_meeting,
)
from database.repositories.repository import (
    catalog_is_current,
    create_repository,
    get_or_create_repository,
    get_repository,
    get_repository_by_source,
    list_repositories,
    row_to_repository,
    save_catalog,
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
    "row_to_repository",
    "save_catalog",
    "update_repository",
    # Meeting
    "create_meeting",
    "get_meeting",
    "list_meetings",
    "row_to_meeting",
    "update_meeting",
    # Idea
    "create_idea",
    "find_idea_by_fingerprint",
    "get_idea",
    "list_ideas",
    "row_to_idea",
    "set_idea_status",
    "update_idea",
    # Attempt
    "create_attempt",
    "get_attempt",
    "list_attempts",
    "row_to_attempt",
    "set_attempt_status",
    "update_attempt",
    # Friction
    "count_friction_by",
    "create_friction_log",
    "list_friction_logs",
    "row_to_friction_log",
]
