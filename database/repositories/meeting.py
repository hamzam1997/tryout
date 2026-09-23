"""Meeting persistence layer."""

import sqlite3

from database.connection import (
    connect,
    dump_model,
    load_model,
    utc_now_iso,
)
from database.models import Meeting, MeetingMinutes, MeetingSource


def row_to_meeting(row: sqlite3.Row) -> Meeting:
    return Meeting(
        id=row["id"],
        title=row["title"],
        occurred_at=row["occurred_at"],
        external_source=MeetingSource(row["external_source"]),
        external_id=row["external_id"],
        external_url=row["external_url"],
        source_type=row["source_type"],
        transcript=row["transcript"],
        minutes=load_model(MeetingMinutes, row["minutes_json"]),
        created_at=row["created_at"],
    )


def create_meeting(meeting: Meeting) -> Meeting:
    created_at = meeting.created_at or utc_now_iso()
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO meeting
               (title, occurred_at, external_source, external_id, external_url,
                source_type, transcript, minutes_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                meeting.title,
                meeting.occurred_at,
                meeting.external_source.value,
                meeting.external_id,
                meeting.external_url,
                meeting.source_type,
                meeting.transcript,
                dump_model(meeting.minutes),
                created_at,
            ),
        )
        return meeting.model_copy(
            update={"id": cur.lastrowid, "created_at": created_at}
        )


def get_meeting(meeting_id: int) -> Meeting | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM meeting WHERE id = ?", (meeting_id,)
        ).fetchone()
    return row_to_meeting(row) if row else None


def list_meetings() -> list[Meeting]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM meeting ORDER BY COALESCE(occurred_at, created_at) DESC"
        ).fetchall()
    return [row_to_meeting(row) for row in rows]


def update_meeting(meeting: Meeting) -> Meeting:
    with connect() as conn:
        conn.execute(
            """UPDATE meeting
               SET title = ?, occurred_at = ?, external_source = ?, external_id = ?,
                   external_url = ?, source_type = ?, transcript = ?, minutes_json = ?
               WHERE id = ?""",
            (
                meeting.title,
                meeting.occurred_at,
                meeting.external_source.value,
                meeting.external_id,
                meeting.external_url,
                meeting.source_type,
                meeting.transcript,
                dump_model(meeting.minutes),
                meeting.id,
            ),
        )
    return meeting
