"""Idea persistence layer using SQLAlchemy."""

from sqlalchemy import select

from database.connection import session_scope, utc_now
from database.models import Idea as IdeaModel
from schemas import Idea, IdeaStatus


def orm_to_idea(orm: IdeaModel) -> Idea:
    return Idea(
        id=orm.id,
        meeting_id=orm.meeting_id,
        title=orm.title,
        description=orm.description,
        source_quote=orm.source_quote,
        speaker=orm.speaker,
        timestamp=orm.timestamp,
        urgency=orm.urgency,
        feasibility_hypothesis=orm.feasibility_hypothesis,
        fingerprint=orm.fingerprint,
        duplicate_of_id=orm.duplicate_of_id,
        status=IdeaStatus(orm.status),
        created_at=orm.created_at,
    )


def create_idea(idea: Idea) -> Idea:
    created_at = idea.created_at or utc_now()
    with session_scope() as session:
        model = IdeaModel(
            meeting_id=idea.meeting_id,
            title=idea.title,
            description=idea.description,
            source_quote=idea.source_quote,
            speaker=idea.speaker,
            timestamp=idea.timestamp,
            urgency=idea.urgency,
            feasibility_hypothesis=idea.feasibility_hypothesis,
            fingerprint=idea.fingerprint,
            duplicate_of_id=idea.duplicate_of_id,
            status=idea.status.value,
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


def find_idea_by_fingerprint(fingerprint: str) -> Idea | None:
    """Return the earliest idea with this fingerprint, for cross-meeting dedup."""
    if not fingerprint:
        return None
    with session_scope() as session:
        stmt = (
            select(IdeaModel)
            .where(IdeaModel.fingerprint == fingerprint)
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


def update_idea(idea: Idea) -> Idea:
    with session_scope() as session:
        model = session.get(IdeaModel, idea.id)
        if model:
            model.title = idea.title
            model.description = idea.description
            model.source_quote = idea.source_quote
            model.speaker = idea.speaker
            model.timestamp = idea.timestamp
            model.urgency = idea.urgency
            model.feasibility_hypothesis = idea.feasibility_hypothesis
            model.fingerprint = idea.fingerprint
            model.duplicate_of_id = idea.duplicate_of_id
            model.status = idea.status.value
    return idea
