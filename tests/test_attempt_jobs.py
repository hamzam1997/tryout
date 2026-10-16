"""Focused tests for the attempt planning and patch workflow."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import database as db
from agents.attempt_jobs import execute_attempt
from agents.harness import HarnessResult
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
        self.plan = TechnicalPlan(
            summary="Change the greeting",
            repo_changes=[PlanStep(order=1, action="edit", target="app.py")],
            external_requirements=["notifications-service"],
        )

    def tearDown(self):
        db.set_database_path(None)
        self.temp.cleanup()

    def test_generates_plan_and_patch_without_running_repo_code(self):
        harness_result = HarnessResult(
            success=True,
            summary="Change the greeting constant.",
            pr_title="Change greeting",
            testing_notes="Tested it.",
            diff="fake diff",
            test_exit_code=0,
        )
        with (
            patch("agents.attempt_jobs.AttemptHarness") as mock_harness_class,
            patch("agents.attempt_jobs.record_friction", return_value=[]),
            patch("agents.attempt_jobs.generate_plan", return_value=self.plan),
            patch(
                "agents.attempt_jobs.create_attempt_pull_request",
                return_value=(
                    "tryout/idea-1-attempt-1",
                    "main",
                    "https://github.com/org/repo/pull/1",
                ),
            ) as create_pr,
        ):
            mock_harness_instance = mock_harness_class.return_value
            mock_harness_instance.run.return_value = harness_result
            
            execute_attempt(self.attempt.id)

        result = db.get_attempt(self.attempt.id)
        self.assertEqual(result.status, AttemptStatus.COMPLETE)
        self.assertEqual(result.plan, self.plan)
        self.assertEqual(mock_harness_class.call_args.kwargs["plan"], self.plan)
        self.assertEqual(result.pull_request_url, "https://github.com/org/repo/pull/1")
        # The PR description reports the tests the attempt actually ran.
        self.assertEqual(create_pr.call_args.kwargs["test_exit_code"], 0)
if __name__ == '__main__':
    unittest.main()
