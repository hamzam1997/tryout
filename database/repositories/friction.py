"""Friction log persistence layer using SQLAlchemy."""

from sqlalchemy import desc, func, select

from database.connection import (
    dump_model_list,
    load_model_list,
    session_scope,
    utc_now,
)
from database.models import FrictionLog as FrictionLogModel
from schemas import FrictionCategory, FrictionLog, ReadinessItem

ALLOWED_COLUMNS = {
    "category": FrictionLogModel.category,
    "service_name": FrictionLogModel.service_name,
    "owning_team": FrictionLogModel.owning_team,
}


def orm_to_friction_log(orm: FrictionLogModel) -> FrictionLog:
    return FrictionLog(
        id=orm.id,
        attempt_id=orm.attempt_id,
        category=FrictionCategory(orm.category),
        service_name=orm.service_name,
        owning_team=orm.owning_team,
        mock_implementation_path=orm.mock_implementation_path,
        required_action=orm.required_action,
        readiness_checklist=load_model_list(
            ReadinessItem, orm.readiness_checklist_json
        ),
        created_at=orm.created_at,
    )


row_to_friction_log = orm_to_friction_log


def create_friction_log(log: FrictionLog) -> FrictionLog:
    created_at = log.created_at or utc_now()
    with session_scope() as session:
        model = FrictionLogModel(
            attempt_id=log.attempt_id,
            category=log.category.value,
            service_name=log.service_name,
            owning_team=log.owning_team,
            mock_implementation_path=log.mock_implementation_path,
            required_action=log.required_action,
            readiness_checklist_json=dump_model_list(log.readiness_checklist),
            created_at=created_at,
        )
        session.add(model)
        session.flush()
        return orm_to_friction_log(model)


def list_friction_logs(attempt_id: int | None = None) -> list[FrictionLog]:
    with session_scope() as session:
        stmt = select(FrictionLogModel)
        if attempt_id is not None:
            stmt = stmt.where(FrictionLogModel.attempt_id == attempt_id)
        stmt = stmt.order_by(FrictionLogModel.id)
        models = session.scalars(stmt).all()
        return [orm_to_friction_log(m) for m in models]


def count_friction_by(column: str) -> list[tuple[str, int]]:
    """Aggregate friction logs for the bottleneck map safely via ORM."""
    if column not in ALLOWED_COLUMNS:
        raise ValueError(f"cannot group friction logs by {column!r}")
    col = ALLOWED_COLUMNS[column]
    with session_scope() as session:
        stmt = (
            select(col.label("key"), func.count().label("total"))
            .where(col != "")
            .group_by(col)
            .order_by(desc("total"), col)
        )
        rows = session.execute(stmt).all()
        return [(row[0], row[1]) for row in rows]
