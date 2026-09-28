"""Meeting persistence layer using SQLAlchemy."""

from sqlalchemy import desc, func, select

from database.connection import (
    dump_model,
    load_model,
    session_scope,
    utc_now,
)
from database.models import Meeting as MeetingModel
from schemas import (
    IdeasExtractStatus,
    Meeting,
    MeetingMinutes,
    MeetingSource,
    MeetingStatus,
)


def orm_to_meeting(orm: MeetingModel) -> Meeting:
    return Meeting(
        id=orm.id,
        title=orm.title,
        occurred_at=orm.occurred_at,
        external_source=MeetingSource(orm.external_source),
        external_id=orm.external_id,
        external_url=orm.external_url,
        transcript=orm.transcript,
        minutes=load_model(MeetingMinutes, orm.minutes_json),
        status=MeetingStatus(orm.status),
        ideas_status=IdeasExtractStatus(orm.ideas_status),
        ideas_error=orm.ideas_error,
        created_at=orm.created_at,
    )


def create_meeting(meeting: Meeting) -> Meeting:
    created_at = meeting.created_at or utc_now()
    with session_scope() as session:
        model = MeetingModel(
            title=meeting.title,
            occurred_at=meeting.occurred_at,
            external_source=meeting.external_source.value,
            external_id=meeting.external_id,
            external_url=meeting.external_url,
            transcript=meeting.transcript,
            minutes_json=dump_model(meeting.minutes),
            status=meeting.status.value,
            ideas_status=meeting.ideas_status.value,
            ideas_error=meeting.ideas_error,
            created_at=created_at,
        )
        session.add(model)
        session.flush()
        return orm_to_meeting(model)


def get_meeting(meeting_id: int) -> Meeting | None:
    with session_scope() as session:
        model = session.get(MeetingModel, meeting_id)
        return orm_to_meeting(model) if model else None


def list_meetings() -> list[Meeting]:
    with session_scope() as session:
        order_col = func.coalesce(MeetingModel.occurred_at, MeetingModel.created_at)
        stmt = select(MeetingModel).order_by(desc(order_col))
        models = session.scalars(stmt).all()
        return [orm_to_meeting(m) for m in models]


def update_meeting(meeting: Meeting) -> Meeting:
    with session_scope() as session:
        model = session.get(MeetingModel, meeting.id)
        if model:
            model.title = meeting.title
            model.occurred_at = meeting.occurred_at
            model.external_source = meeting.external_source.value
            model.external_id = meeting.external_id
            model.external_url = meeting.external_url
            model.transcript = meeting.transcript
            model.minutes_json = dump_model(meeting.minutes)
            model.status = meeting.status.value
            model.ideas_status = meeting.ideas_status.value
            model.ideas_error = meeting.ideas_error
    return meeting


def set_meeting_status(meeting_id: int, status: MeetingStatus) -> None:
    """Move a meeting through the ingest -> extract pipeline."""
    with session_scope() as session:
        model = session.get(MeetingModel, meeting_id)
        if model:
            model.status = status.value


def set_meeting_ideas_state(
    meeting_id: int,
    ideas_status: IdeasExtractStatus,
    ideas_error: str | None = None,
) -> None:
    """Update background idea-extraction status and optional error message."""
    with session_scope() as session:
        model = session.get(MeetingModel, meeting_id)
        if model:
            model.ideas_status = ideas_status.value
            model.ideas_error = ideas_error


def set_meeting_ideas_error(meeting_id: int, ideas_error: str | None) -> None:
    """Record or clear the last idea-extraction failure for a meeting."""
    with session_scope() as session:
        model = session.get(MeetingModel, meeting_id)
        if model:
            model.ideas_error = ideas_error
            if ideas_error:
                model.ideas_status = IdeasExtractStatus.FAILED.value
            elif model.ideas_status == IdeasExtractStatus.FAILED.value:
                model.ideas_status = IdeasExtractStatus.PROCESSED.value


def delete_meeting(meeting_id: int) -> bool:
    """Delete a meeting and cascaded ideas/attempts. Returns False if missing."""
    with session_scope() as session:
        model = session.get(MeetingModel, meeting_id)
        if model is None:
            return False
        session.delete(model)
        return True
