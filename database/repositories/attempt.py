"""Attempt persistence layer."""

import sqlite3

from database.connection import (
    connect,
    dump_model,
    load_model,
    utc_now_iso,
)
from database.models import Attempt, AttemptStatus, TechnicalPlan


def row_to_attempt(row: sqlite3.Row) -> Attempt:
    return Attempt(
        id=row["id"],
        idea_id=row["idea_id"],
        repository_id=row["repository_id"],
        repo_ref=row["repo_ref"],
        status=AttemptStatus(row["status"]),
        plan=load_model(TechnicalPlan, row["plan_json"]),
        diff=row["diff"],
        test_exit_code=row["test_exit_code"],
        test_stdout=row["test_stdout"],
        test_stderr=row["test_stderr"],
        error=row["error"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        created_at=row["created_at"],
    )


def create_attempt(attempt: Attempt) -> Attempt:
    created_at = attempt.created_at or utc_now_iso()
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO attempt
               (idea_id, repository_id, repo_ref, status, plan_json, diff,
                test_exit_code, test_stdout, test_stderr, error,
                started_at, finished_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                attempt.idea_id,
                attempt.repository_id,
                attempt.repo_ref,
                attempt.status.value,
                dump_model(attempt.plan),
                attempt.diff,
                attempt.test_exit_code,
                attempt.test_stdout,
                attempt.test_stderr,
                attempt.error,
                attempt.started_at,
                attempt.finished_at,
                created_at,
            ),
        )
        return attempt.model_copy(
            update={"id": cur.lastrowid, "created_at": created_at}
        )


def get_attempt(attempt_id: int) -> Attempt | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM attempt WHERE id = ?", (attempt_id,)
        ).fetchone()
    return row_to_attempt(row) if row else None


def list_attempts(idea_id: int | None = None) -> list[Attempt]:
    sql = "SELECT * FROM attempt"
    params: list[object] = []
    if idea_id is not None:
        sql += " WHERE idea_id = ?"
        params.append(idea_id)
    sql += " ORDER BY id DESC"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [row_to_attempt(row) for row in rows]


def set_attempt_status(
    attempt_id: int, status: AttemptStatus, error: str | None = None
) -> None:
    """Advance an attempt, stamping start and finish times at the boundaries."""
    now = utc_now_iso()
    is_active = status in (
        AttemptStatus.PLANNING,
        AttemptStatus.CODING,
        AttemptStatus.TESTING,
    )
    is_terminal = status in (AttemptStatus.COMPLETE, AttemptStatus.FAILED)

    with connect() as conn:
        row = conn.execute(
            "SELECT started_at, finished_at, error FROM attempt WHERE id = ?",
            (attempt_id,),
        ).fetchone()
        if not row:
            return

        existing_started_at = row["started_at"]
        existing_finished_at = row["finished_at"]
        existing_error = row["error"]

        if is_active or is_terminal:
            started_at = existing_started_at or now
        else:
            started_at = existing_started_at

        if is_terminal:
            finished_at = now
        else:
            finished_at = None

        new_error = (
            error
            if error is not None
            else (existing_error if status is AttemptStatus.FAILED else None)
        )

        conn.execute(
            """UPDATE attempt
               SET status = ?,
                   error = ?,
                   started_at = ?,
                   finished_at = ?
               WHERE id = ?""",
            (status.value, new_error, started_at, finished_at, attempt_id),
        )


def update_attempt(attempt: Attempt) -> Attempt:
    with connect() as conn:
        conn.execute(
            """UPDATE attempt
               SET repo_ref = ?, status = ?, plan_json = ?, diff = ?,
                   test_exit_code = ?, test_stdout = ?, test_stderr = ?, error = ?,
                   started_at = ?, finished_at = ?
               WHERE id = ?""",
            (
                attempt.repo_ref,
                attempt.status.value,
                dump_model(attempt.plan),
                attempt.diff,
                attempt.test_exit_code,
                attempt.test_stdout,
                attempt.test_stderr,
                attempt.error,
                attempt.started_at,
                attempt.finished_at,
                attempt.id,
            ),
        )
    return attempt
