import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import database as db
from app import app
from schemas import Attempt, AttemptStatus, AttemptStep, FrictionCategory, FrictionLog, Idea, Meeting, Repository


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


class TestAttemptStream(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.set_database_path(Path(self.tmp.name) / "database")
        db.init_db()
        self.client = app.test_client()
        meeting = db.create_meeting(Meeting(title="Sync", transcript="t"))
        idea = db.create_idea(Idea(meeting_id=meeting.id, title="Idea"))
        repo = db.create_repository(Repository(name="r", source="/tmp/r"))
        now = datetime.now(timezone.utc)
        self.attempt = db.create_attempt(Attempt(
            idea_id=idea.id, repository_id=repo.id, status=AttemptStatus.COMPLETE,
            events=[AttemptStep(timestamp=now, action="view_file", detail="a.py"),
                    AttemptStep(timestamp=now, action="complete", detail="done")],
        ))

    def tearDown(self):
        db.set_database_path(None)
        self.tmp.cleanup()

    def test_finished_attempt_streams_all_steps_then_done(self):
        body = self.client.get(f"/attempts/{self.attempt.id}/stream").get_data(as_text=True)
        self.assertEqual(body.count("event: step"), 2)
        self.assertIn("id: 2\nevent: step", body)
        self.assertTrue(body.rstrip().endswith('data: {"status": "COMPLETE"}'))

    def test_reconnect_resumes_after_last_event_id(self):
        body = self.client.get(
            f"/attempts/{self.attempt.id}/stream", headers={"Last-Event-ID": "1"}
        ).get_data(as_text=True)
        self.assertEqual(body.count("event: step"), 1)
        self.assertIn('"action": "complete"', body)

    def test_missing_attempt_is_404(self):
        self.assertEqual(self.client.get("/attempts/999/stream").status_code, 404)
