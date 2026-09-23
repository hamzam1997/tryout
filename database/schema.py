"""SQLite DDL schema and initialization."""

from database.connection import connect, database_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS repository (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    source TEXT NOT NULL UNIQUE,
    source_type TEXT NOT NULL,
    source_ref TEXT,
    catalog_json TEXT,
    catalog_generated_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meeting (
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

CREATE TABLE IF NOT EXISTS idea (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER NOT NULL REFERENCES meeting(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    source_quote TEXT NOT NULL DEFAULT '',
    speaker TEXT NOT NULL DEFAULT '',
    timestamp TEXT NOT NULL DEFAULT '',
    urgency TEXT NOT NULL DEFAULT '',
    feasibility_hypothesis TEXT NOT NULL DEFAULT '',
    fingerprint TEXT NOT NULL DEFAULT '',
    duplicate_of_id INTEGER REFERENCES idea(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attempt (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    idea_id INTEGER NOT NULL REFERENCES idea(id) ON DELETE CASCADE,
    repository_id INTEGER NOT NULL REFERENCES repository(id) ON DELETE CASCADE,
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

CREATE TABLE IF NOT EXISTS friction_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL REFERENCES attempt(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    service_name TEXT NOT NULL DEFAULT '',
    owning_team TEXT NOT NULL DEFAULT '',
    mock_implementation_path TEXT NOT NULL DEFAULT '',
    required_action TEXT NOT NULL DEFAULT '',
    readiness_checklist_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_idea_meeting ON idea(meeting_id);
CREATE INDEX IF NOT EXISTS idx_idea_fingerprint ON idea(fingerprint);
CREATE INDEX IF NOT EXISTS idx_idea_status ON idea(status);
CREATE INDEX IF NOT EXISTS idx_attempt_idea ON attempt(idea_id);
CREATE INDEX IF NOT EXISTS idx_friction_attempt ON friction_log(attempt_id);
CREATE INDEX IF NOT EXISTS idx_friction_category ON friction_log(category);
CREATE INDEX IF NOT EXISTS idx_friction_service ON friction_log(service_name);
CREATE INDEX IF NOT EXISTS idx_friction_team ON friction_log(owning_team);
"""


def init_db() -> None:
    """Create tables and indexes if they do not exist, and set WAL mode."""
    database_path().parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
