"""Meeting persistence layer using SQLAlchemy."""

from sqlalchemy import desc, func, select

from database.connection import (
    dump_model,
    load_model,
    session_scope,
    utc_now_iso,
)
from database.models import Meeting as MeetingModel
from database.schemas import Meeting, MeetingMinutes, MeetingSource


def orm_to_meeting(orm: MeetingModel) -> Meeting:
    return Meeting(
        id=orm.id,
        title=orm.title,
        occurred_at=orm.occurred_at,
        external_source=MeetingSource(orm.external_source),
        external_id=orm.external_id,
        external_url=orm.external_url,
        source_type=orm.source_type,
        transcript=orm.transcript,
        minutes=load_model(MeetingMinutes, orm.minutes_json),
        created_at=orm.created_at,
    )


row_to_meeting = orm_to_meeting


def create_meeting(meeting: Meeting) -> Meeting:
    created_at = meeting.created_at or utc_now_iso()
    with session_scope() as session:
        model = MeetingModel(
            title=meeting.title,
            occurred_at=meeting.occurred_at,
            external_source=meeting.external_source.value,
            external_id=meeting.external_id,
            external_url=meeting.external_url,
            source_type=meeting.source_type,
            transcript=meeting.transcript,
            minutes_json=dump_model(meeting.minutes),
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
            model.source_type = meeting.source_type
            model.transcript = meeting.transcript
            model.minutes_json = dump_model(meeting.minutes)
    return meeting
