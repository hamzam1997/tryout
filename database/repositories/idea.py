"""Idea persistence layer using SQLAlchemy."""

import json

from sqlalchemy import select

from database.connection import session_scope, utc_now
from database.models import Idea as IdeaModel
from schemas import Idea, IdeaStatus


def _load_catalog_refs(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _dump_catalog_refs(refs: list[str] | None) -> str:
    return json.dumps(list(refs or []))


def orm_to_idea(orm: IdeaModel) -> Idea:
    return Idea(
        id=orm.id,
        meeting_id=orm.meeting_id,
        title=orm.title,
        description=orm.description,
        quote=orm.quote,
        speaker=orm.speaker,
        cue_time=orm.cue_time,
        priority=orm.priority,
        attempt_hypothesis=orm.attempt_hypothesis,
        catalog_refs=_load_catalog_refs(orm.catalog_refs_json),
        idea_key=orm.idea_key,
        original_idea_id=orm.original_idea_id,
        status=IdeaStatus(orm.status),
        approved_by=orm.approved_by,
        approved_at=orm.approved_at,
        created_at=orm.created_at,
    )


def create_idea(idea: Idea) -> Idea:
    created_at = idea.created_at or utc_now()
    with session_scope() as session:
        model = IdeaModel(
            meeting_id=idea.meeting_id,
            title=idea.title,
            description=idea.description,
            quote=idea.quote,
            speaker=idea.speaker,
            cue_time=idea.cue_time,
            priority=idea.priority,
            attempt_hypothesis=idea.attempt_hypothesis,
            catalog_refs_json=_dump_catalog_refs(idea.catalog_refs),
            idea_key=idea.idea_key,
            original_idea_id=idea.original_idea_id,
            status=idea.status.value,
            approved_by=idea.approved_by,
            approved_at=idea.approved_at,
            created_at=created_at,
        )
        session.add(model)
        session.flush()
        return orm_to_idea(model)


def get_idea(idea_id: int) -> Idea | None:
    with session_scope() as session:
        model = session.get(IdeaModel, idea_id)
        return orm_to_idea(model) if model else None


def list_ideas(
    status: IdeaStatus | None = None, meeting_id: int | None = None
) -> list[Idea]:
    with session_scope() as session:
        stmt = select(IdeaModel)
        if status is not None:
            stmt = stmt.where(IdeaModel.status == status.value)
        if meeting_id is not None:
            stmt = stmt.where(IdeaModel.meeting_id == meeting_id)
        stmt = stmt.order_by(IdeaModel.id)
        models = session.scalars(stmt).all()
        return [orm_to_idea(m) for m in models]


def find_idea_by_key(idea_key: str) -> Idea | None:
    """Return the earliest idea with this idea_key, for cross-meeting dedup."""
    if not idea_key:
        return None
    with session_scope() as session:
        stmt = (
            select(IdeaModel)
            .where(IdeaModel.idea_key == idea_key)
            .order_by(IdeaModel.id)
            .limit(1)
        )
        model = session.scalars(stmt).first()
        return orm_to_idea(model) if model else None


def set_idea_status(idea_id: int, status: IdeaStatus) -> None:
    with session_scope() as session:
        model = session.get(IdeaModel, idea_id)
        if model:
            model.status = status.value


def approve_idea(idea_id: int, approved_by: str) -> Idea | None:
    """Approve an idea and move it to IN_PROCESS as work starts."""
    reviewer = (approved_by or "").strip()
    if not reviewer:
        raise ValueError("approved_by is required")

    with session_scope() as session:
        model = session.get(IdeaModel, idea_id)
        if model is None:
            return None
        model.status = IdeaStatus.IN_PROCESS.value
        model.approved_by = reviewer
        model.approved_at = utc_now()
        session.flush()
        return orm_to_idea(model)


def update_idea(idea: Idea) -> Idea:
    with session_scope() as session:
        model = session.get(IdeaModel, idea.id)
        if model:
            model.title = idea.title
            model.description = idea.description
            model.quote = idea.quote
            model.speaker = idea.speaker
            model.cue_time = idea.cue_time
            model.priority = idea.priority
            model.attempt_hypothesis = idea.attempt_hypothesis
            model.catalog_refs_json = _dump_catalog_refs(idea.catalog_refs)
            model.idea_key = idea.idea_key
            model.original_idea_id = idea.original_idea_id
            model.status = idea.status.value
            model.approved_by = idea.approved_by
            model.approved_at = idea.approved_at
    return idea


def delete_idea(idea_id: int) -> bool:
    """Delete an idea and cascaded attempts. Returns False if missing."""
    with session_scope() as session:
        model = session.get(IdeaModel, idea_id)
        if model is None:
            return False
        session.delete(model)
        return True
