"""Upload ingestion: persistence order, status transitions, and retry."""

import io
import logging
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import database as db
from agents import meeting_jobs

# The app calls init_db() at import, so point it somewhere disposable first.
_BOOTSTRAP = tempfile.TemporaryDirectory()
db.set_database_path(Path(_BOOTSTRAP.name) / "bootstrap.db")

import app as flask_app  # noqa: E402
from agents.note_taker import NoteTakerError  # noqa: E402
from schemas import Idea, MeetingMinutes, MeetingSource, MeetingStatus  # noqa: E402

VTT = """WEBVTT

00:00:04.100 --> 00:00:09.800
<v Marco Reyes>Can we email customers when a refund is delayed?

00:00:10.200 --> 00:00:14.600
<v Priya Raman>We'd need to know why it's delayed.
"""

MINUTES = MeetingMinutes(
    summary="Discussed notifying customers about delayed refunds.",
    key_points=["Refund delays are invisible to the customer"],
    action_items=["Priya to scope the store-side work"],
)


def upload(client, content=VTT, filename="weekly-ops.vtt", **form):
    data = {"file": (io.BytesIO(content.encode()), filename), **form}
    return client.post(
        "/api/meetings/upload", data=data, content_type="multipart/form-data"
    )


class IngestionTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        db.set_database_path(Path(self._tmp.name) / "test.db")
        db.init_db()
        self.client = flask_app.app.test_client()
        # The failure-path tests exercise logger.exception on purpose.
        logging.getLogger("agents.note_taker").setLevel(logging.CRITICAL)
        logging.getLogger("agents.meeting_jobs").setLevel(logging.CRITICAL)
        # Run minutes inline so assertions see the finished state.
        meeting_jobs.set_force_sync(True)
        # Idea extraction is a background event after minutes; keep note tests focused.
        self._ideas_patch = mock.patch("agents.idea_jobs.on_minutes_ready")
        self._ideas_patch.start()

    def tearDown(self):
        self._ideas_patch.stop()
        meeting_jobs.set_force_sync(False)
        db.set_database_path(None)
        self._tmp.cleanup()


class TestSuccessfulUpload(IngestionTestCase):
    @mock.patch("agents.note_taker.generate_minutes", return_value=MINUTES)
    def test_upload_stores_meeting_and_minutes(self, _):
        response = upload(self.client, title="Weekly Ops")
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.get_json()["minutes_queued"])

        body = response.get_json()
        self.assertEqual(body["format"], "vtt")
        self.assertEqual(body["speakers"], ["Marco Reyes", "Priya Raman"])
        self.assertEqual(body["cue_count"], 2)

        meeting = body["meeting"]
        self.assertEqual(meeting["title"], "Weekly Ops")
        self.assertEqual(meeting["status"], MeetingStatus.PROCESSED.value)
        self.assertEqual(meeting["external_source"], MeetingSource.UPLOAD.value)
        self.assertEqual(
            meeting["minutes"]["action_items"], ["Priya to scope the store-side work"]
        )

    @mock.patch("agents.note_taker.generate_minutes", return_value=MINUTES)
    def test_cue_times_survive_into_the_stored_transcript(self, _):
        """TRY-302 reads these back out to fill Idea.cue_time."""
        body = upload(self.client).get_json()
        self.assertIn("[00:00:04] Marco Reyes:", body["meeting"]["transcript"])

    @mock.patch("agents.note_taker.generate_minutes", return_value=MINUTES)
    def test_title_falls_back_to_the_filename(self, _):
        body = upload(self.client, filename="2026-09-17-weekly-ops.vtt").get_json()
        self.assertEqual(body["meeting"]["title"], "2026-09-17-weekly-ops")

    @mock.patch("agents.note_taker.generate_minutes", return_value=MINUTES)
    def test_occurred_at_is_accepted_and_stored(self, _):
        body = upload(self.client, occurred_at="2026-09-17T10:00:00+00:00").get_json()
        self.assertTrue(body["meeting"]["occurred_at"].startswith("2026-09-17T10:00"))

    @mock.patch("agents.note_taker.generate_minutes", return_value=MINUTES)
    def test_plain_text_upload_is_accepted(self, _):
        body = upload(
            self.client, content="Marco: hello there", filename="notes.txt"
        ).get_json()
        self.assertEqual(body["format"], "text")


class TestModelFailure(IngestionTestCase):
    @mock.patch(
        "agents.note_taker.generate_minutes", side_effect=NoteTakerError("boom")
    )
    def test_transcript_survives_a_failed_model_call(self, _):
        """Persist-before-extract: a Gemini failure must not lose the upload."""
        response = upload(self.client, title="Weekly Ops")
        # Upload accepts immediately; the background job records the failure.
        self.assertEqual(response.status_code, 202)

        stored = db.list_meetings()
        self.assertEqual(len(stored), 1)
        self.assertIn("Can we email customers", stored[0].transcript)

    @mock.patch(
        "agents.note_taker.generate_minutes", side_effect=NoteTakerError("boom")
    )
    def test_failure_is_recorded_as_FAILED_not_left_pending(self, _):
        """The distinction minutes-is-null could never express."""
        upload(self.client)
        meeting = db.list_meetings()[0]
        self.assertEqual(meeting.status, MeetingStatus.FAILED)
        self.assertIsNone(meeting.minutes)


class TestRejections(IngestionTestCase):
    def test_missing_file_rejected(self):
        response = self.client.post(
            "/api/meetings/upload", data={}, content_type="multipart/form-data"
        )
        self.assertEqual(response.status_code, 400)

    def test_unsupported_extension_rejected(self):
        self.assertEqual(upload(self.client, filename="audio.mp3").status_code, 400)

    def test_non_utf8_upload_rejected(self):
        data = {"file": (io.BytesIO(b"\xff\xfe\x00bad"), "notes.vtt")}
        response = self.client.post(
            "/api/meetings/upload", data=data, content_type="multipart/form-data"
        )
        self.assertEqual(response.status_code, 400)

    def test_unparseable_transcript_rejected_before_insert(self):
        """A bad file must not leave a row behind."""
        response = upload(self.client, content="   ", filename="empty.vtt")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(db.list_meetings(), [])

    def test_bad_occurred_at_rejected(self):
        response = upload(self.client, occurred_at="last Tuesday")
        self.assertEqual(response.status_code, 400)


class TestReadEndpoints(IngestionTestCase):
    @mock.patch("agents.note_taker.generate_minutes", return_value=MINUTES)
    def test_list_and_get(self, _):
        meeting_id = upload(self.client).get_json()["meeting"]["id"]

        listed = self.client.get("/api/meetings").get_json()
        self.assertEqual(len(listed), 1)
        self.assertNotIn("transcript", listed[0])
        self.assertIn("speakers", listed[0])

        fetched = self.client.get(f"/api/meetings/{meeting_id}").get_json()
        self.assertEqual(fetched["id"], meeting_id)
        self.assertIn("transcript", fetched)
        self.assertIsNotNone(fetched.get("minutes"))

    def test_get_unknown_meeting_is_404(self):
        self.assertEqual(self.client.get("/api/meetings/9999").status_code, 404)

    @mock.patch("agents.note_taker.generate_minutes", return_value=MINUTES)
    def test_duplicate_transcript_reuses_meeting(self, _):
        first = upload(self.client, title="Weekly Ops")
        self.assertEqual(first.status_code, 202)
        first_id = first.get_json()["meeting"]["id"]

        second = upload(self.client, title="Weekly Ops again")
        self.assertEqual(second.status_code, 200)
        body = second.get_json()
        self.assertTrue(body["duplicate"])
        self.assertFalse(body["minutes_queued"])
        self.assertEqual(body["meeting"]["id"], first_id)
        self.assertEqual(len(db.list_meetings()), 1)

    @mock.patch("agents.note_taker.generate_minutes", return_value=MINUTES)
    def test_delete_meeting_cascades_ideas(self, _):
        meeting_id = upload(self.client).get_json()["meeting"]["id"]
        db.create_idea(
            Idea(
                meeting_id=meeting_id,
                title="Notify delayed refunds",
                idea_key="notify-delayed-refunds",
            )
        )
        self.assertEqual(len(db.list_ideas(meeting_id=meeting_id)), 1)

        response = self.client.delete(f"/api/meetings/{meeting_id}")
        self.assertEqual(response.status_code, 204)
        self.assertIsNone(db.get_meeting(meeting_id))
        self.assertEqual(db.list_ideas(meeting_id=meeting_id), [])
        self.assertEqual(self.client.delete("/api/meetings/9999").status_code, 404)


if __name__ == "__main__":
    unittest.main()
