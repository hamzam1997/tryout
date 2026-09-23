"""Friction log persistence layer."""

import sqlite3

from database.connection import (
    connect,
    dump_model_list,
    load_model_list,
    utc_now_iso,
)
from database.models import FrictionCategory, FrictionLog, ReadinessItem

ALLOWED_GROUPING_COLUMNS = {
    "category": "category",
    "service_name": "service_name",
    "owning_team": "owning_team",
}


def row_to_friction_log(row: sqlite3.Row) -> FrictionLog:
    return FrictionLog(
        id=row["id"],
        attempt_id=row["attempt_id"],
        category=FrictionCategory(row["category"]),
        service_name=row["service_name"],
        owning_team=row["owning_team"],
        mock_implementation_path=row["mock_implementation_path"],
        required_action=row["required_action"],
        readiness_checklist=load_model_list(
            ReadinessItem, row["readiness_checklist_json"]
        ),
        created_at=row["created_at"],
    )


def create_friction_log(log: FrictionLog) -> FrictionLog:
    created_at = log.created_at or utc_now_iso()
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO friction_log
               (attempt_id, category, service_name, owning_team,
                mock_implementation_path, required_action,
                readiness_checklist_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                log.attempt_id,
                log.category.value,
                log.service_name,
                log.owning_team,
                log.mock_implementation_path,
                log.required_action,
                dump_model_list(log.readiness_checklist),
                created_at,
            ),
        )
        return log.model_copy(update={"id": cur.lastrowid, "created_at": created_at})


def list_friction_logs(attempt_id: int | None = None) -> list[FrictionLog]:
    sql = "SELECT * FROM friction_log"
    params: list[object] = []
    if attempt_id is not None:
        sql += " WHERE attempt_id = ?"
        params.append(attempt_id)
    sql += " ORDER BY id"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [row_to_friction_log(row) for row in rows]


def count_friction_by(column: str) -> list[tuple[str, int]]:
    """Aggregate friction logs for the bottleneck map."""
    if column not in ALLOWED_GROUPING_COLUMNS:
        raise ValueError(f"cannot group friction logs by {column!r}")
    safe_col = ALLOWED_GROUPING_COLUMNS[column]
    with connect() as conn:
        rows = conn.execute(
            f"""SELECT {safe_col} AS key, COUNT(*) AS total
                FROM friction_log
                WHERE {safe_col} != ''
                GROUP BY {safe_col}
                ORDER BY total DESC, key"""
        ).fetchall()
    return [(row["key"], row["total"]) for row in rows]
