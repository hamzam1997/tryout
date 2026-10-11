"""Tests for background minutes/idea extraction and retry queuing."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import database as db
from agents import idea_jobs, meeting_jobs
from agents.idea_extractor import IdeaExtractorError
from app import app
from schemas import IdeasExtractStatus, Meeting, MeetingSource, MeetingStatus

VTT = """WEBVTT

00:00:04.100 --> 00:00:09.800
<v Marco Reyes>Can we email customers when a refund is delayed?
"""


class TestMeetingIdeasRetry(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        db.set_database_path(Path(self._tmp.name) / "test.db")
        db.init_db()
        idea_jobs.set_force_sync(True)
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
        idea_jobs.set_force_sync(False)
        db.set_database_path(None)
        self._tmp.cleanup()

    def test_extract_ideas_persists_error(self):
        with patch(
            "agents.idea_jobs.extract_ideas",
            side_effect=IdeaExtractorError("catalog missing"),
        ):
            response = self.client.post(f"/api/meetings/{self.meeting.id}/extract-ideas")

        self.assertEqual(response.status_code, 202)
        meeting = db.get_meeting(self.meeting.id)
        self.assertEqual(meeting.ideas_status, IdeasExtractStatus.FAILED)
        self.assertEqual(meeting.ideas_error, "catalog missing")

    def test_extract_ideas_clears_error_on_success(self):
        db.set_meeting_ideas_state(
            self.meeting.id,
            IdeasExtractStatus.FAILED,
            ideas_error="old failure",
        )
        with patch("agents.idea_jobs.extract_ideas", return_value=[]):
            response = self.client.post(f"/api/meetings/{self.meeting.id}/extract-ideas")

        self.assertEqual(response.status_code, 202)
        meeting = db.get_meeting(self.meeting.id)
        self.assertEqual(meeting.ideas_status, IdeasExtractStatus.PROCESSED)
        self.assertIsNone(meeting.ideas_error)

    def test_extract_ideas_requires_processed_minutes(self):
        pending = db.create_meeting(
            Meeting(
                title="Pending",
                transcript="x",
                status=MeetingStatus.PENDING,
            )
        )
        response = self.client.post(f"/api/meetings/{pending.id}/extract-ideas")
        self.assertEqual(response.status_code, 409)

    def test_minutes_ready_queues_idea_job(self):
        with patch("agents.idea_jobs.extract_ideas", return_value=[]) as mocked:
            idea_jobs.on_minutes_ready(self.meeting.id)

        mocked.assert_called_once_with(self.meeting.id)
        meeting = db.get_meeting(self.meeting.id)
        self.assertEqual(meeting.ideas_status, IdeasExtractStatus.PROCESSED)


class TestMeetingMinutesBackground(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        db.set_database_path(Path(self._tmp.name) / "test.db")
        db.init_db()
        meeting_jobs.set_force_sync(False)
        self.client = app.test_client()

    def tearDown(self):
        meeting_jobs.set_force_sync(False)
        db.set_database_path(None)
        self._tmp.cleanup()

    @patch("agents.meeting_jobs.threading.Thread")
    def test_upload_queues_minutes_in_background(self, mock_thread):
        data = {"file": (io.BytesIO(VTT.encode()), "ops.vtt"), "title": "Ops"}
        response = self.client.post(
            "/api/meetings/upload", data=data, content_type="multipart/form-data"
        )

        self.assertEqual(response.status_code, 202)
        body = response.get_json()
        self.assertTrue(body["minutes_queued"])
        self.assertEqual(body["meeting"]["status"], MeetingStatus.PROCESSING.value)
        mock_thread.assert_called_once()
        mock_thread.return_value.start.assert_called_once()


if __name__ == "__main__":
    unittest.main()
