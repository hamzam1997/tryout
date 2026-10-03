"""Focused tests for the attempt planning and patch workflow."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import database as db
from agents.attempt_agent import FileChange, FileChangeBatch
from agents.attempt_jobs import execute_attempt
from schemas import (
    ArchitectureCatalog,
    Attempt,
    AttemptStatus,
    Idea,
    IdeaStatus,
    FileRole,
    Meeting,
    PlanStep,
    RepoSource,
    Repository,
    TechnicalPlan,
)


class TestAttemptJobs(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo_path = self.root / "repo"
        self.repo_path.mkdir()
        (self.repo_path / "app.py").write_text("MESSAGE = 'before'\n", encoding="utf-8")
        db.set_database_path(self.root / "database")
        db.init_db()
        self.meeting = db.create_meeting(
            Meeting(title="Planning", transcript="Change the greeting")
        )
        self.idea = db.create_idea(
            Idea(
                meeting_id=self.meeting.id,
                title="Change greeting",
                description="Update the greeting in app.py.",
                quote="Change the greeting",
                catalog_refs=["app.py"],
            )
        )
        self.repository = db.create_repository(
            Repository(
                name="Demo",
                source=str(self.repo_path),
                source_type=RepoSource.LOCAL,
                catalog=ArchitectureCatalog(
                    name="Demo",
                    test_command="touch should-not-run",
                    key_files=[FileRole(path="app.py", role="Greeting constant")],
                ),
                catalog_status="ready",
            )
        )
        self.attempt = db.create_attempt(
            Attempt(idea_id=self.idea.id, repository_id=self.repository.id)
        )

    def tearDown(self):
        db.set_database_path(None)
        self.temp.cleanup()

    def test_generates_plan_and_patch_without_running_repo_code(self):
        plan = TechnicalPlan(
            summary="Change the greeting constant.",
            repo_changes=[PlanStep(order=1, action="Update the message", target="app.py")],
        )
        changes = FileChangeBatch(
            changes=[
                FileChange(path="app.py", content="MESSAGE = 'after'\n"),
                FileChange(
                    path="test_prototype.py",
                    content="from app import MESSAGE\n\ndef test_message():\n    assert MESSAGE == 'after'\n",
                ),
            ]
        )
        with (
            patch("agents.attempt_jobs.generate_plan", return_value=plan),
            patch("agents.coder.generate_changes", return_value=changes),
            patch(
                "agents.attempt_jobs.create_attempt_pull_request",
                return_value=(
                    "tryout/idea-1-attempt-1",
                    "main",
                    "https://github.com/org/repo/pull/1",
                ),
            ),
        ):
            execute_attempt(self.attempt.id)

        result = db.get_attempt(self.attempt.id)
        self.assertEqual(result.status, AttemptStatus.COMPLETE)
        self.assertEqual(result.pull_request_url, "https://github.com/org/repo/pull/1")
        self.assertEqual(result.plan.summary, plan.summary)
        self.assertIn("MESSAGE = 'after'", result.diff)
        self.assertIn("Tests were not run", result.test_stdout)
        self.assertIsNone(result.test_exit_code)
        self.assertFalse((self.repo_path / "should-not-run").exists())
        self.assertEqual(
            (self.repo_path / "app.py").read_text(encoding="utf-8"), "MESSAGE = 'before'\n"
        )
        self.assertEqual(db.get_idea(self.idea.id).status, IdeaStatus.DONE)


if __name__ == "__main__":
    unittest.main()
