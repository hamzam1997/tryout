"""Idea persistence layer."""

import sqlite3

from database.connection import connect, utc_now_iso
from database.models import Idea, IdeaStatus


def row_to_idea(row: sqlite3.Row) -> Idea:
    return Idea(
        id=row["id"],
        meeting_id=row["meeting_id"],
        title=row["title"],
        description=row["description"],
        source_quote=row["source_quote"],
        speaker=row["speaker"],
        timestamp=row["timestamp"],
        urgency=row["urgency"],
        feasibility_hypothesis=row["feasibility_hypothesis"],
        fingerprint=row["fingerprint"],
        duplicate_of_id=row["duplicate_of_id"],
        status=IdeaStatus(row["status"]),
        created_at=row["created_at"],
    )


def create_idea(idea: Idea) -> Idea:
    created_at = idea.created_at or utc_now_iso()
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO idea
               (meeting_id, title, description, source_quote, speaker, timestamp,
                urgency, feasibility_hypothesis, fingerprint, duplicate_of_id,
                status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                idea.meeting_id,
                idea.title,
                idea.description,
                idea.source_quote,
                idea.speaker,
                idea.timestamp,
                idea.urgency,
                idea.feasibility_hypothesis,
                idea.fingerprint,
                idea.duplicate_of_id,
                idea.status.value,
                created_at,
            ),
        )
        return idea.model_copy(update={"id": cur.lastrowid, "created_at": created_at})


def get_idea(idea_id: int) -> Idea | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM idea WHERE id = ?", (idea_id,)).fetchone()
    return row_to_idea(row) if row else None


def list_ideas(
    status: IdeaStatus | None = None, meeting_id: int | None = None
) -> list[Idea]:
    sql = "SELECT * FROM idea"
    clauses: list[str] = []
    params: list[object] = []
    if status is not None:
        clauses.append("status = ?")
        params.append(status.value)
    if meeting_id is not None:
        clauses.append("meeting_id = ?")
        params.append(meeting_id)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY id"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [row_to_idea(row) for row in rows]


def find_idea_by_fingerprint(fingerprint: str) -> Idea | None:
    """Return the earliest idea with this fingerprint, for cross-meeting dedup."""
    if not fingerprint:
        return None
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM idea WHERE fingerprint = ? ORDER BY id LIMIT 1",
            (fingerprint,),
        ).fetchone()
    return row_to_idea(row) if row else None


def set_idea_status(idea_id: int, status: IdeaStatus) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE idea SET status = ? WHERE id = ?", (status.value, idea_id)
        )


def update_idea(idea: Idea) -> Idea:
    with connect() as conn:
        conn.execute(
            """UPDATE idea
               SET title = ?, description = ?, source_quote = ?, speaker = ?,
                   timestamp = ?, urgency = ?, feasibility_hypothesis = ?,
                   fingerprint = ?, duplicate_of_id = ?, status = ?
               WHERE id = ?""",
            (
                idea.title,
                idea.description,
                idea.source_quote,
                idea.speaker,
                idea.timestamp,
                idea.urgency,
                idea.feasibility_hypothesis,
                idea.fingerprint,
                idea.duplicate_of_id,
                idea.status.value,
                idea.id,
            ),
        )
    return idea
