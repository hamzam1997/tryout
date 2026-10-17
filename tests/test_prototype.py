import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import database as db
from agents.attempt_jobs import execute_attempt
from integrations.mock_slack_client import MockSlackClient
from schemas import (
    Attempt,
    Idea,
    Meeting,
    Repository,
    RepoSource,
)

class TestPrototypeNotification(unittest.TestCase):
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
                name="demo",
                source=str(self.repo_path),
                source_type=RepoSource.LOCAL,
                catalog=None,
            )
        )
        # Attempt without catalog to fail fast
        self.attempt = db.create_attempt(
            Attempt(
                idea_id=self.idea.id,
                repository_id=self.repository.id,
            )
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_slack_notification_sent_on_completion(self):
        mock_client = MockSlackClient()
        execute_attempt(self.attempt.id, notification_client=mock_client)
        
        self.assertEqual(len(mock_client.calls), 1)
        self.assertEqual(mock_client.calls[0]["attempt_id"], self.attempt.id)
        self.assertTrue(mock_client.calls[0]["report_link"].endswith(f"/attempts/{self.attempt.id}"))
