"""Friction classification persists blockers and never breaks an attempt."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import database as db
from agents.friction_classifier import FrictionItem, readiness_markdown, record_friction
from schemas import ArchitectureCatalog, Attempt, FrictionCategory, Idea, Meeting, ReadinessItem, Repository


class TestFrictionClassifier(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        db.set_database_path(Path(self.temp.name) / "database")
        db.init_db()
        meeting = db.create_meeting(Meeting(title="Sync", transcript="t"))
        self.idea = db.create_idea(Idea(meeting_id=meeting.id, title="Refund alert"))
        repo = db.create_repository(Repository(name="r", source="/tmp/r"))
        self.attempt = db.create_attempt(Attempt(idea_id=self.idea.id, repository_id=repo.id))

    def tearDown(self):
        db.set_database_path(None)
        self.temp.cleanup()

    def _record(self):
        return record_friction(
            self.attempt, self.idea, ArchitectureCatalog(name="r"), "diff", "notes", "model"
        )

    def test_blockers_are_persisted_and_rendered(self):
        item = FrictionItem(
            category=FrictionCategory.EXTERNAL_SERVICE_DEPENDENCY,
            service_name="notifications-service",
            owning_team="@team-comms",
            mock_implementation_path="integrations/mock_notifications_client.py",
            required_action="Expose a send-notification endpoint.",
            readiness_checklist=[ReadinessItem(task="Grant NOTIFY_API_KEY", owner="@team-comms")],
        )
        with patch("agents.friction_classifier.classify_friction", return_value=[item]):
            logs = self._record()
        stored = db.list_friction_logs(attempt_id=self.attempt.id)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].owning_team, "@team-comms")
        self.assertEqual(len(logs), 1)
        md = readiness_markdown(stored)
        self.assertIn("- [ ] Grant NOTIFY_API_KEY — @team-comms", md)

    def test_model_failure_is_swallowed(self):
        with patch("agents.friction_classifier.classify_friction", side_effect=RuntimeError("boom")):
            self.assertEqual(self._record(), [])
        self.assertEqual(db.list_friction_logs(attempt_id=self.attempt.id), [])
        self.assertEqual(readiness_markdown([]), "")


if __name__ == "__main__":
    unittest.main()
