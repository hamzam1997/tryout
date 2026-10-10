"""Unit tests for the catalog-grounded idea extractor."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import database as db
from agents.idea_extractor import (
    IdeaExtractorError,
    extract_ideas,
    generate_ideas,
    normalize_idea_key,
)
from config import BASE_DIR
from schemas import (
    ArchitectureCatalog,
    ExtractedIdeaBatch,
    ExtractedIdeaCandidate,
    Idea,
    IdeaStatus,
    ModuleDescription,
    RouteEntry,
)


class TestIdeaExtractor(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        db.set_database_path(Path(self._tmp.name) / "test.db")
        db.init_db()

        self.catalog = ArchitectureCatalog(
            name="acme_store",
            language="Python",
            framework="Flask",
            summary="Store service for orders and refunds.",
            modules=[
                ModuleDescription(
                    name="Payments & Refunds",
                    path="routes/refunds.py",
                    description="Refund processing",
                )
            ],
            api_routes=[
                RouteEntry(
                    method="POST",
                    path="/refunds",
                    handler="process_refund",
                    file_path="routes/refunds.py",
                )
            ],
            external_dependencies=["notifications-service (@team-comms)"],
        )

        self.meeting = db.create_meeting(
            db.Meeting(
                title="Weekly ops",
                transcript=(
                    "[00:00:46] Marco Reyes: automatically email the customer "
                    "that it's still in progress."
                ),
            )
        )

        self.sample_batch = ExtractedIdeaBatch(
            ideas=[
                ExtractedIdeaCandidate(
                    title="Auto-notify customers on delayed refunds",
                    description="Email customers when refunds sit in progress too long.",
                    quote="automatically email the customer that it's still in progress",
                    speaker="Marco Reyes",
                    cue_time="00:00:46",
                    priority="high",
                    attempt_hypothesis=(
                        "Track refund age in routes/refunds.py; outbound email via "
                        "notifications-service is external."
                    ),
                    catalog_refs=["routes/refunds.py", "notifications-service"],
                    idea_key="auto-notify-delayed-refunds",
                )
            ]
        )

    def tearDown(self):
        db.set_database_path(None)
        self._tmp.cleanup()

    def _mock_generate_client(self, batch: ExtractedIdeaBatch | None = None):
        batch = batch or self.sample_batch
        mock_response = MagicMock()
        mock_response.parsed = batch
        mock_response.text = batch.model_dump_json()
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        return mock_client

    def test_normalize_idea_key(self):
        self.assertEqual(
            normalize_idea_key("Auto Notify Delayed Refunds"),
            "auto-notify-delayed-refunds",
        )

    @patch("agents.idea_extractor.get_client")
    def test_generate_ideas_includes_catalog_markdown(self, mock_get_client):
        mock_get_client.return_value = self._mock_generate_client()
        generate_ideas("Alice: hello", self.catalog, title="Sync", meeting_id=1)

        call_kwargs = mock_get_client.return_value.models.generate_content.call_args
        prompt = call_kwargs.kwargs["contents"]
        self.assertIn("Architecture catalog for the target repository:", prompt)
        self.assertIn("routes/refunds.py", prompt)
        self.assertIn("notifications-service", prompt)
        self.assertIn("Transcript:", prompt)
        self.assertIn("Alice: hello", prompt)
        config = call_kwargs.kwargs["config"]
        self.assertEqual(config.response_schema, ExtractedIdeaBatch)

    @patch("agents.idea_extractor.RepoOnboarder")
    @patch("agents.idea_extractor.get_client")
    def test_catalog_grounded_idea_persists(self, mock_get_client, mock_onboarder_cls):
        mock_onboarder_cls.return_value.onboard.return_value = self.catalog
        mock_get_client.return_value = self._mock_generate_client()

        ideas = extract_ideas(self.meeting.id, repository=BASE_DIR / "demo_repo" / "acme_store")

        self.assertEqual(len(ideas), 1)
        idea = db.get_idea(ideas[0].id)
        self.assertEqual(idea.catalog_refs, ["routes/refunds.py", "notifications-service"])
        self.assertIn("routes/refunds.py", idea.attempt_hypothesis)
        self.assertEqual(idea.idea_key, "auto-notify-delayed-refunds")
        self.assertEqual(idea.status, IdeaStatus.PENDING)

    @patch("agents.idea_extractor.RepoOnboarder")
    @patch("agents.idea_extractor.get_client")
    def test_empty_batch_creates_no_rows(self, mock_get_client, mock_onboarder_cls):
        mock_onboarder_cls.return_value.onboard.return_value = self.catalog
        mock_get_client.return_value = self._mock_generate_client(ExtractedIdeaBatch())

        ideas = extract_ideas(self.meeting.id)
        self.assertEqual(ideas, [])
        self.assertEqual(len(db.list_ideas(meeting_id=self.meeting.id)), 0)

    @patch("agents.idea_extractor._repos_with_catalog", return_value=["broken", "demo"])
    @patch("agents.idea_extractor.RepoOnboarder")
    @patch("agents.idea_extractor.get_client")
    def test_each_repo_extracted_and_one_failure_tolerated(
        self, mock_get_client, mock_onboarder_cls, _targets
    ):
        mock_onboarder_cls.return_value.onboard.side_effect = [ValueError("scan failed"), self.catalog]
        mock_get_client.return_value = self._mock_generate_client()

        ideas = extract_ideas(self.meeting.id)
        self.assertEqual(len(ideas), 1)

    @patch("agents.idea_extractor.RepoOnboarder")
    @patch("agents.idea_extractor.get_client")
    def test_saved_repository_catalog_is_used_without_onboarding(
        self, mock_get_client, mock_onboarder_cls
    ):
        saved = db.create_repository(
            db.Repository(name="acme", source="https://github.com/org/private", catalog=self.catalog)
        )
        mock_get_client.return_value = self._mock_generate_client()

        ideas = extract_ideas(self.meeting.id)

        mock_onboarder_cls.return_value.onboard.assert_not_called()
        self.assertEqual(len(ideas), 1)
        self.assertEqual(db.get_idea(ideas[0].id).repository_id, saved.id)

    @patch("agents.idea_extractor.RepoOnboarder")
    def test_onboard_failure_raises_without_rows(self, mock_onboarder_cls):
        mock_onboarder_cls.return_value.onboard.side_effect = ValueError("scan failed")

        with self.assertRaises(IdeaExtractorError):
            extract_ideas(self.meeting.id)

        self.assertEqual(len(db.list_ideas(meeting_id=self.meeting.id)), 0)

    @patch("agents.idea_extractor.RepoOnboarder")
    @patch("agents.idea_extractor.get_client")
    def test_idea_key_dedup_skips_existing(self, mock_get_client, mock_onboarder_cls):
        mock_onboarder_cls.return_value.onboard.return_value = self.catalog
        mock_get_client.return_value = self._mock_generate_client()

        original = db.create_idea(
            Idea(
                meeting_id=self.meeting.id,
                title="Prior mention",
                idea_key="auto-notify-delayed-refunds",
                catalog_refs=["routes/refunds.py"],
            )
        )

        second_meeting = db.create_meeting(
            db.Meeting(title="Follow-up", transcript="Marco: same auto email idea.")
        )
        mock_get_client.return_value = self._mock_generate_client()

        ideas = extract_ideas(second_meeting.id)
        self.assertEqual(ideas, [])
        matching = [
            idea
            for idea in db.list_ideas()
            if idea.idea_key == "auto-notify-delayed-refunds"
        ]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].id, original.id)


if __name__ == "__main__":
    unittest.main()
