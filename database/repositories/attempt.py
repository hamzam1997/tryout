"""Attempt persistence layer using SQLAlchemy."""

from sqlalchemy import desc, select

from database.connection import (
    dump_model,
    load_model,
    session_scope,
    utc_now_iso,
)
from database.models import Attempt as AttemptModel
from database.schemas import Attempt, AttemptStatus, TechnicalPlan


def orm_to_attempt(orm: AttemptModel) -> Attempt:
    return Attempt(
        id=orm.id,
        idea_id=orm.idea_id,
        repository_id=orm.repository_id,
        repo_ref=orm.repo_ref,
        status=AttemptStatus(orm.status),
        plan=load_model(TechnicalPlan, orm.plan_json),
        diff=orm.diff,
        test_exit_code=orm.test_exit_code,
        test_stdout=orm.test_stdout,
        test_stderr=orm.test_stderr,
        error=orm.error,
        started_at=orm.started_at,
        finished_at=orm.finished_at,
        created_at=orm.created_at,
    )


row_to_attempt = orm_to_attempt


def create_attempt(attempt: Attempt) -> Attempt:
    created_at = attempt.created_at or utc_now_iso()
    with session_scope() as session:
        model = AttemptModel(
            idea_id=attempt.idea_id,
            repository_id=attempt.repository_id,
            repo_ref=attempt.repo_ref,
            status=attempt.status.value,
            plan_json=dump_model(attempt.plan),
            diff=attempt.diff,
            test_exit_code=attempt.test_exit_code,
            test_stdout=attempt.test_stdout,
            test_stderr=attempt.test_stderr,
            error=attempt.error,
            started_at=attempt.started_at,
            finished_at=attempt.finished_at,
            created_at=created_at,
        )
        session.add(model)
        session.flush()
        return orm_to_attempt(model)


def get_attempt(attempt_id: int) -> Attempt | None:
    with session_scope() as session:
        model = session.get(AttemptModel, attempt_id)
        return orm_to_attempt(model) if model else None


def list_attempts(idea_id: int | None = None) -> list[Attempt]:
    with session_scope() as session:
        stmt = select(AttemptModel)
        if idea_id is not None:
            stmt = stmt.where(AttemptModel.idea_id == idea_id)
        stmt = stmt.order_by(desc(AttemptModel.id))
        models = session.scalars(stmt).all()
        return [orm_to_attempt(m) for m in models]


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

    with session_scope() as session:
        model = session.get(AttemptModel, attempt_id)
        if not model:
            return

        model.status = status.value

        if is_active or is_terminal:
            model.started_at = model.started_at or now

        if is_terminal:
            model.finished_at = now
        else:
            model.finished_at = None

        if error is not None:
            model.error = error
        elif status is AttemptStatus.COMPLETE:
            model.error = None


def update_attempt(attempt: Attempt) -> Attempt:
    with session_scope() as session:
        model = session.get(AttemptModel, attempt.id)
        if model:
            model.repo_ref = attempt.repo_ref
            model.status = attempt.status.value
            model.plan_json = dump_model(attempt.plan)
            model.diff = attempt.diff
            model.test_exit_code = attempt.test_exit_code
            model.test_stdout = attempt.test_stdout
            model.test_stderr = attempt.test_stderr
            model.error = attempt.error
            model.started_at = attempt.started_at
            model.finished_at = attempt.finished_at
    return attempt
