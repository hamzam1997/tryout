"""Tests for persisting idea-extraction errors and retrying extraction."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import database as db
from agents.idea_extractor import IdeaExtractorError
from app import app
from schemas import Meeting, MeetingSource, MeetingStatus


class TestMeetingIdeasRetry(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        db.set_database_path(Path(self._tmp.name) / "test.db")
        db.init_db()
        self.client = app.test_client()
        self.meeting = db.create_meeting(
            Meeting(
                title="Ops huddle",
                transcript="Marco: auto notify delayed refunds?",
                external_source=MeetingSource.SEED,
                status=MeetingStatus.PROCESSED,
            )
        )

    def tearDown(self):
        db.set_database_path(None)
        self._tmp.cleanup()

    def test_extract_ideas_persists_error(self):
        with patch(
            "views.meetings.extract_ideas",
            side_effect=IdeaExtractorError("catalog missing"),
        ):
            response = self.client.post(f"/meetings/{self.meeting.id}/extract-ideas")

        self.assertEqual(response.status_code, 502)
        body = response.get_json()
        self.assertEqual(body["ideas_error"], "catalog missing")
        self.assertEqual(body["meeting"]["ideas_error"], "catalog missing")
        self.assertEqual(db.get_meeting(self.meeting.id).ideas_error, "catalog missing")

    def test_extract_ideas_clears_error_on_success(self):
        db.set_meeting_ideas_error(self.meeting.id, "old failure")
        with patch("views.meetings.extract_ideas", return_value=[]):
            response = self.client.post(f"/meetings/{self.meeting.id}/extract-ideas")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get_json()["meeting"]["ideas_error"])
        self.assertIsNone(db.get_meeting(self.meeting.id).ideas_error)

    def test_extract_ideas_requires_processed_minutes(self):
        pending = db.create_meeting(
            Meeting(
                title="Pending",
                transcript="x",
                status=MeetingStatus.PENDING,
            )
        )
        response = self.client.post(f"/meetings/{pending.id}/extract-ideas")
        self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
