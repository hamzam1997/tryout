"""HTTP tests for the ideas inbox endpoints."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import database as db
from app import app
from schemas import Idea, IdeaStatus, Meeting, MeetingSource


class TestIdeasApi(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        db.set_database_path(Path(self._tmp.name) / "test.db")
        db.init_db()
        self.client = app.test_client()
        self.meeting = db.create_meeting(
            Meeting(
                title="Weekly ops",
                transcript="Marco: Can we auto-notify delayed refunds?",
                external_source=MeetingSource.SEED,
            )
        )
        self.idea = db.create_idea(
            Idea(
                meeting_id=self.meeting.id,
                title="Auto-notify delayed refunds",
                description="Email customers when a refund sits too long.",
                quote="Can we auto-notify delayed refunds?",
                speaker="Marco Reyes",
                cue_time="00:00:46",
                priority="high",
                attempt_hypothesis="Extend refunds routes; mock notifications-service.",
                catalog_refs=["routes/refunds.py", "notifications-service"],
                idea_key="auto-notify-delayed-refunds",
                status=IdeaStatus.PENDING,
            )
        )

    def tearDown(self):
        db.set_database_path(None)
        self._tmp.cleanup()

    def test_list_ideas_includes_meeting_title(self):
        response = self.client.get("/ideas")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["title"], self.idea.title)
        self.assertEqual(body[0]["meeting_title"], "Weekly ops")
        self.assertEqual(body[0]["catalog_refs"], ["routes/refunds.py", "notifications-service"])

    def test_list_ideas_filters_by_status(self):
        db.set_idea_status(self.idea.id, IdeaStatus.APPROVED)
        pending = self.client.get("/ideas?status=PENDING")
        approved = self.client.get("/ideas?status=APPROVED")
        self.assertEqual(pending.get_json(), [])
        self.assertEqual(len(approved.get_json()), 1)

    def test_approve_and_reject_gates(self):
        approved = self.client.post(
            f"/ideas/{self.idea.id}/approve",
            json={"approved_by": "dana"},
        )
        self.assertEqual(approved.status_code, 200)
        body = approved.get_json()
        self.assertEqual(body["status"], "IN_PROCESS")
        self.assertEqual(body["approved_by"], "dana")
        self.assertIsNotNone(body["approved_at"])

        again = self.client.post(f"/ideas/{self.idea.id}/approve")
        self.assertEqual(again.status_code, 409)

        other = db.create_idea(
            Idea(
                meeting_id=self.meeting.id,
                title="Other",
                idea_key="other",
                status=IdeaStatus.PENDING,
            )
        )
        rejected = self.client.post(f"/ideas/{other.id}/reject")
        self.assertEqual(rejected.status_code, 200)
        self.assertEqual(rejected.get_json()["status"], "REJECTED")

    def test_get_missing_idea(self):
        response = self.client.get("/ideas/9999")
        self.assertEqual(response.status_code, 404)

    def test_delete_idea(self):
        response = self.client.delete(f"/ideas/{self.idea.id}")
        self.assertEqual(response.status_code, 204)
        self.assertIsNone(db.get_idea(self.idea.id))
        self.assertIsNotNone(db.get_meeting(self.meeting.id))

        missing = self.client.delete("/ideas/9999")
        self.assertEqual(missing.status_code, 404)

    def test_get_idea_detail_vs_summary(self):
        # Summary from list_ideas does not include heavy fields
        list_resp = self.client.get("/ideas")
        self.assertEqual(list_resp.status_code, 200)
        summary = list_resp.get_json()[0]
        self.assertNotIn("description", summary)
        self.assertNotIn("attempt_hypothesis", summary)
        self.assertNotIn("quote", summary)

        # GET /ideas/<id> returns all details
        detail_resp = self.client.get(f"/ideas/{self.idea.id}")
        self.assertEqual(detail_resp.status_code, 200)
        detail = detail_resp.get_json()
        self.assertEqual(detail["id"], self.idea.id)
        self.assertEqual(detail["description"], self.idea.description)
        self.assertEqual(detail["attempt_hypothesis"], self.idea.attempt_hypothesis)
        self.assertEqual(detail["quote"], self.idea.quote)

    def test_get_idea_counts(self):
        resp = self.client.get("/ideas/counts")
        self.assertEqual(resp.status_code, 200)
        counts = resp.get_json()
        self.assertEqual(counts["PENDING"], 1)
        self.assertEqual(counts["IN_PROCESS"], 0)
        self.assertEqual(counts["ALL"], 1)


if __name__ == "__main__":
    unittest.main()
