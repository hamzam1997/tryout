"""SQLite persistence layer."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterator

from pydantic import BaseModel

from config import settings

BUSY_TIMEOUT_MS = 5000

_db_path: Path | None = None


class RepoSource(str, Enum):
    GITHUB = "github"
    LOCAL = "local"
    DEMO = "demo"


class MeetingSource(str, Enum):
    MEET = "meet"
    UPLOAD = "upload"
    PASTE = "paste"
    SEED = "seed"


class IdeaStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AttemptStatus(str, Enum):
    QUEUED = "QUEUED"
    PLANNING = "PLANNING"
    CODING = "CODING"
    TESTING = "TESTING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class FrictionCategory(str, Enum):
    EXTERNAL_SERVICE_DEPENDENCY = "EXTERNAL_SERVICE_DEPENDENCY"
    AUTH_CREDENTIAL_REQUIRED = "AUTH_CREDENTIAL_REQUIRED"
    SCHEMA_MIGRATION_REQUIRED = "SCHEMA_MIGRATION_REQUIRED"
    CROSS_TEAM_CONTRACT = "CROSS_TEAM_CONTRACT"
    PRODUCT_DECISION = "PRODUCT_DECISION"


class ModelEntry(BaseModel):
    name: str
    fields: list[str] = []


class RouteEntry(BaseModel):
    method: str = ""
    path: str
    handler: str = ""


class IntegrationEntry(BaseModel):
    name: str
    auth: str = ""
    env_keys: list[str] = []


class ArchitectureCatalog(BaseModel):
    name: str = ""
    language: str = ""
    framework: str = ""
    summary: str = ""
    internal_models: list[ModelEntry] = []
    api_routes: list[RouteEntry] = []
    external_integrations: list[IntegrationEntry] = []
    config_schema: list[str] = []
    codeowners: dict[str, str] = {}


class MeetingMinutes(BaseModel):
    summary: str = ""
    key_points: list[str] = []
    action_items: list[str] = []


class PlanStep(BaseModel):
    order: int
    action: str
    target: str = ""
    rationale: str = ""


class TechnicalPlan(BaseModel):
    summary: str = ""
    repo_changes: list[PlanStep] = []
    external_requirements: list[str] = []
    mock_strategy: str = ""


class ReadinessItem(BaseModel):
    task: str
    owner: str = ""
    done: bool = False


class Repository(BaseModel):
    id: int | None = None
    name: str
    source: str
    source_type: RepoSource = RepoSource.LOCAL
    source_ref: str | None = None
    catalog: ArchitectureCatalog | None = None
    catalog_generated_at: str | None = None
    created_at: str | None = None


class Meeting(BaseModel):
    id: int | None = None
    title: str
    occurred_at: str | None = None
    external_source: MeetingSource = MeetingSource.PASTE
    external_id: str | None = None
    external_url: str | None = None
    source_type: str | None = None
    transcript: str
    minutes: MeetingMinutes | None = None
    created_at: str | None = None


class Idea(BaseModel):
    id: int | None = None
    meeting_id: int
    title: str
    description: str = ""
    source_quote: str = ""
    speaker: str = ""
    timestamp: str = ""
    urgency: str = ""
    feasibility_hypothesis: str = ""
    fingerprint: str = ""
    duplicate_of_id: int | None = None
    status: IdeaStatus = IdeaStatus.PENDING
    created_at: str | None = None


class Attempt(BaseModel):
    id: int | None = None
    idea_id: int
    repository_id: int
    repo_ref: str | None = None
    status: AttemptStatus = AttemptStatus.QUEUED
    plan: TechnicalPlan | None = None
    diff: str | None = None
    test_exit_code: int | None = None
    test_stdout: str | None = None
    test_stderr: str | None = None
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    created_at: str | None = None


class FrictionLog(BaseModel):
    id: int | None = None
    attempt_id: int
    category: FrictionCategory
    service_name: str = ""
    owning_team: str = ""
    mock_implementation_path: str = ""
    required_action: str = ""
    readiness_checklist: list[ReadinessItem] = []
    created_at: str | None = None


SCHEMA = """
CREATE TABLE IF NOT EXISTS repositories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    source TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_ref TEXT,
    catalog_json TEXT,
    catalog_generated_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meetings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    occurred_at TEXT,
    external_source TEXT NOT NULL,
    external_id TEXT,
    external_url TEXT,
    source_type TEXT,
    transcript TEXT NOT NULL,
    minutes_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ideas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    source_quote TEXT NOT NULL DEFAULT '',
    speaker TEXT NOT NULL DEFAULT '',
    timestamp TEXT NOT NULL DEFAULT '',
    urgency TEXT NOT NULL DEFAULT '',
    feasibility_hypothesis TEXT NOT NULL DEFAULT '',
    fingerprint TEXT NOT NULL DEFAULT '',
    duplicate_of_id INTEGER REFERENCES ideas(id),
    status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    idea_id INTEGER NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
    repository_id INTEGER NOT NULL REFERENCES repositories(id),
    repo_ref TEXT,
    status TEXT NOT NULL DEFAULT 'QUEUED',
    plan_json TEXT,
    diff TEXT,
    test_exit_code INTEGER,
    test_stdout TEXT,
    test_stderr TEXT,
    error TEXT,
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS friction_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    service_name TEXT NOT NULL DEFAULT '',
    owning_team TEXT NOT NULL DEFAULT '',
    mock_implementation_path TEXT NOT NULL DEFAULT '',
    required_action TEXT NOT NULL DEFAULT '',
    readiness_checklist_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ideas_meeting ON ideas(meeting_id);
CREATE INDEX IF NOT EXISTS idx_ideas_fingerprint ON ideas(fingerprint);
CREATE INDEX IF NOT EXISTS idx_ideas_status ON ideas(status);
CREATE INDEX IF NOT EXISTS idx_attempts_idea ON attempts(idea_id);
CREATE INDEX IF NOT EXISTS idx_friction_attempt ON friction_logs(attempt_id);
CREATE INDEX IF NOT EXISTS idx_friction_category ON friction_logs(category);
CREATE INDEX IF NOT EXISTS idx_friction_service ON friction_logs(service_name);
CREATE INDEX IF NOT EXISTS idx_friction_team ON friction_logs(owning_team);
"""


def set_database_path(path: Path | str | None) -> None:
    """Override the database location. Used by tests."""
    global _db_path
    _db_path = Path(path) if path is not None else None


def database_path() -> Path:
    return _db_path if _db_path is not None else settings.database_path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dump(model: BaseModel | None) -> str | None:
    return model.model_dump_json() if model is not None else None


def _load[T: BaseModel](cls: type[T], raw: str | None) -> T | None:
    return cls.model_validate_json(raw) if raw else None


def _dump_list(models: list[BaseModel]) -> str:
    return json.dumps([m.model_dump() for m in models])


def _load_list[T: BaseModel](cls: type[T], raw: str | None) -> list[T]:
    return [cls.model_validate(item) for item in json.loads(raw)] if raw else []


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Open a connection, committing on success and rolling back on error."""
    conn = sqlite3.connect(database_path(), timeout=BUSY_TIMEOUT_MS / 1000)
    conn.row_factory = sqlite3.Row
    # WAL keeps readers unblocked while an attempt writes; foreign keys are off
    # by default in SQLite and must be enabled per connection.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create tables and indexes if they do not exist."""
    database_path().parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)


def _to_repository(row: sqlite3.Row) -> Repository:
    return Repository(
        id=row["id"],
        name=row["name"],
        source=row["source"],
        source_type=RepoSource(row["source_type"]),
        source_ref=row["source_ref"],
        catalog=_load(ArchitectureCatalog, row["catalog_json"]),
        catalog_generated_at=row["catalog_generated_at"],
        created_at=row["created_at"],
    )


def _to_meeting(row: sqlite3.Row) -> Meeting:
    return Meeting(
        id=row["id"],
        title=row["title"],
        occurred_at=row["occurred_at"],
        external_source=MeetingSource(row["external_source"]),
        external_id=row["external_id"],
        external_url=row["external_url"],
        source_type=row["source_type"],
        transcript=row["transcript"],
        minutes=_load(MeetingMinutes, row["minutes_json"]),
        created_at=row["created_at"],
    )


def _to_idea(row: sqlite3.Row) -> Idea:
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


def _to_attempt(row: sqlite3.Row) -> Attempt:
    return Attempt(
        id=row["id"],
        idea_id=row["idea_id"],
        repository_id=row["repository_id"],
        repo_ref=row["repo_ref"],
        status=AttemptStatus(row["status"]),
        plan=_load(TechnicalPlan, row["plan_json"]),
        diff=row["diff"],
        test_exit_code=row["test_exit_code"],
        test_stdout=row["test_stdout"],
        test_stderr=row["test_stderr"],
        error=row["error"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        created_at=row["created_at"],
    )


def _to_friction_log(row: sqlite3.Row) -> FrictionLog:
    return FrictionLog(
        id=row["id"],
        attempt_id=row["attempt_id"],
        category=FrictionCategory(row["category"]),
        service_name=row["service_name"],
        owning_team=row["owning_team"],
        mock_implementation_path=row["mock_implementation_path"],
        required_action=row["required_action"],
        readiness_checklist=_load_list(ReadinessItem, row["readiness_checklist_json"]),
        created_at=row["created_at"],
    )


def create_repository(repo: Repository) -> Repository:
    created_at = repo.created_at or _now()
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO repositories
               (name, source, source_type, source_ref, catalog_json,
                catalog_generated_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                repo.name,
                repo.source,
                repo.source_type.value,
                repo.source_ref,
                _dump(repo.catalog),
                repo.catalog_generated_at,
                created_at,
            ),
        )
        return repo.model_copy(update={"id": cur.lastrowid, "created_at": created_at})


def get_repository(repo_id: int) -> Repository | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM repositories WHERE id = ?", (repo_id,)
        ).fetchone()
    return _to_repository(row) if row else None


def get_repository_by_source(source: str) -> Repository | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM repositories WHERE source = ?", (source,)
        ).fetchone()
    return _to_repository(row) if row else None


def list_repositories() -> list[Repository]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM repositories ORDER BY id").fetchall()
    return [_to_repository(row) for row in rows]


def get_or_create_repository(repo: Repository) -> Repository:
    existing = get_repository_by_source(repo.source)
    return existing if existing else create_repository(repo)


def update_repository(repo: Repository) -> Repository:
    with connect() as conn:
        conn.execute(
            """UPDATE repositories
               SET name = ?, source = ?, source_type = ?, source_ref = ?,
                   catalog_json = ?, catalog_generated_at = ?
               WHERE id = ?""",
            (
                repo.name,
                repo.source,
                repo.source_type.value,
                repo.source_ref,
                _dump(repo.catalog),
                repo.catalog_generated_at,
                repo.id,
            ),
        )
    return repo


def save_catalog(
    repo_id: int, catalog: ArchitectureCatalog, source_ref: str | None = None
) -> None:
    """Cache a generated catalog against the repo state it was built from."""
    with connect() as conn:
        conn.execute(
            """UPDATE repositories
               SET catalog_json = ?, catalog_generated_at = ?, source_ref = ?
               WHERE id = ?""",
            (catalog.model_dump_json(), _now(), source_ref, repo_id),
        )


def catalog_is_current(repo: Repository, source_ref: str | None) -> bool:
    """True when a cached catalog exists and the repo has not moved since."""
    return (
        repo.catalog is not None
        and repo.source_ref is not None
        and repo.source_ref == source_ref
    )


def create_meeting(meeting: Meeting) -> Meeting:
    created_at = meeting.created_at or _now()
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO meetings
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
                _dump(meeting.minutes),
                created_at,
            ),
        )
        return meeting.model_copy(
            update={"id": cur.lastrowid, "created_at": created_at}
        )


def get_meeting(meeting_id: int) -> Meeting | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM meetings WHERE id = ?", (meeting_id,)
        ).fetchone()
    return _to_meeting(row) if row else None


def list_meetings() -> list[Meeting]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM meetings ORDER BY COALESCE(occurred_at, created_at) DESC"
        ).fetchall()
    return [_to_meeting(row) for row in rows]


def update_meeting(meeting: Meeting) -> Meeting:
    with connect() as conn:
        conn.execute(
            """UPDATE meetings
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
                _dump(meeting.minutes),
                meeting.id,
            ),
        )
    return meeting


def create_idea(idea: Idea) -> Idea:
    created_at = idea.created_at or _now()
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO ideas
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
        row = conn.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,)).fetchone()
    return _to_idea(row) if row else None


def list_ideas(
    status: IdeaStatus | None = None, meeting_id: int | None = None
) -> list[Idea]:
    sql = "SELECT * FROM ideas"
    clauses, params = [], []
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
    return [_to_idea(row) for row in rows]


def find_idea_by_fingerprint(fingerprint: str) -> Idea | None:
    """Return the earliest idea with this fingerprint, for cross-meeting dedup."""
    if not fingerprint:
        return None
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM ideas WHERE fingerprint = ? ORDER BY id LIMIT 1",
            (fingerprint,),
        ).fetchone()
    return _to_idea(row) if row else None


def set_idea_status(idea_id: int, status: IdeaStatus) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE ideas SET status = ? WHERE id = ?", (status.value, idea_id)
        )


def update_idea(idea: Idea) -> Idea:
    with connect() as conn:
        conn.execute(
            """UPDATE ideas
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


def create_attempt(attempt: Attempt) -> Attempt:
    created_at = attempt.created_at or _now()
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO attempts
               (idea_id, repository_id, repo_ref, status, plan_json, diff,
                test_exit_code, test_stdout, test_stderr, error,
                started_at, finished_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                attempt.idea_id,
                attempt.repository_id,
                attempt.repo_ref,
                attempt.status.value,
                _dump(attempt.plan),
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
            "SELECT * FROM attempts WHERE id = ?", (attempt_id,)
        ).fetchone()
    return _to_attempt(row) if row else None


def list_attempts(idea_id: int | None = None) -> list[Attempt]:
    sql = "SELECT * FROM attempts"
    params: list[object] = []
    if idea_id is not None:
        sql += " WHERE idea_id = ?"
        params.append(idea_id)
    sql += " ORDER BY id DESC"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_to_attempt(row) for row in rows]


def set_attempt_status(
    attempt_id: int, status: AttemptStatus, error: str | None = None
) -> None:
    """Advance an attempt, stamping start and finish times at the boundaries."""
    started_at = _now() if status is AttemptStatus.PLANNING else None
    finished_at = (
        _now()
        if status in (AttemptStatus.COMPLETE, AttemptStatus.FAILED)
        else None
    )
    with connect() as conn:
        conn.execute(
            """UPDATE attempts
               SET status = ?,
                   error = COALESCE(?, error),
                   started_at = COALESCE(started_at, ?),
                   finished_at = COALESCE(?, finished_at)
               WHERE id = ?""",
            (status.value, error, started_at, finished_at, attempt_id),
        )


def update_attempt(attempt: Attempt) -> Attempt:
    with connect() as conn:
        conn.execute(
            """UPDATE attempts
               SET repo_ref = ?, status = ?, plan_json = ?, diff = ?,
                   test_exit_code = ?, test_stdout = ?, test_stderr = ?, error = ?,
                   started_at = ?, finished_at = ?
               WHERE id = ?""",
            (
                attempt.repo_ref,
                attempt.status.value,
                _dump(attempt.plan),
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


def create_friction_log(log: FrictionLog) -> FrictionLog:
    created_at = log.created_at or _now()
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO friction_logs
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
                _dump_list(log.readiness_checklist),
                created_at,
            ),
        )
        return log.model_copy(update={"id": cur.lastrowid, "created_at": created_at})


def list_friction_logs(attempt_id: int | None = None) -> list[FrictionLog]:
    sql = "SELECT * FROM friction_logs"
    params: list[object] = []
    if attempt_id is not None:
        sql += " WHERE attempt_id = ?"
        params.append(attempt_id)
    sql += " ORDER BY id"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_to_friction_log(row) for row in rows]


def count_friction_by(column: str) -> list[tuple[str, int]]:
    """Aggregate friction logs for the bottleneck map."""
    allowed = {"category", "service_name", "owning_team"}
    if column not in allowed:
        raise ValueError(f"cannot group friction logs by {column!r}")
    with connect() as conn:
        rows = conn.execute(
            f"""SELECT {column} AS key, COUNT(*) AS total
                FROM friction_logs
                WHERE {column} != ''
                GROUP BY {column}
                ORDER BY total DESC, key"""
        ).fetchall()
    return [(row["key"], row["total"]) for row in rows]
