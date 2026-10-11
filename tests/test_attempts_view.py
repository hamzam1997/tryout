import tempfile
import unittest
from pathlib import Path

import database as db
from app import app
from schemas import Attempt, FrictionCategory, FrictionLog, Idea, Meeting, Repository


class TestAttemptsView(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.set_database_path(Path(self.tmp.name) / "database")
        db.init_db()
        self.client = app.test_client()

    def tearDown(self):
        db.set_database_path(None)
        self.tmp.cleanup()

    def test_missing_attempt_is_404(self):
        self.assertEqual(self.client.get("/attempts/999").status_code, 404)

    def test_report_includes_idea_title_and_friction(self):
        meeting = db.create_meeting(Meeting(title="Sync", transcript="t"))
        idea = db.create_idea(Idea(meeting_id=meeting.id, title="Refund alert"))
        repo = db.create_repository(Repository(name="r", source="/tmp/r"))
        attempt = db.create_attempt(Attempt(idea_id=idea.id, repository_id=repo.id, diff="d"))
        db.create_friction_log(FrictionLog(
            attempt_id=attempt.id, category=FrictionCategory.PRODUCT_DECISION, service_name="x",
        ))

        body = self.client.get(f"/attempts/{attempt.id}").get_json()

        self.assertEqual(body["idea_title"], "Refund alert")
        self.assertEqual(body["diff"], "d")
        self.assertEqual([f["category"] for f in body["friction"]], ["PRODUCT_DECISION"])


if __name__ == "__main__":
    unittest.main()
