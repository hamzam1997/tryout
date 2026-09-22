import sqlite3
import tempfile
import unittest
from pathlib import Path

import database as db


class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        db.set_database_path(Path(self._tmp.name) / "test.db")
        db.init_db()

    def tearDown(self):
        db.set_database_path(None)
        self._tmp.cleanup()

    def make_repository(self, source="/tmp/acme-store"):
        return db.create_repository(
            db.Repository(
                name="acme-store", source=source, source_type=db.RepoSource.DEMO
            )
        )

    def make_meeting(self):
        return db.create_meeting(
            db.Meeting(
                title="Acme Weekly Ops Sync",
                transcript="Ana: refunds are silently delayed.",
                external_source=db.MeetingSource.SEED,
            )
        )

    def make_idea(self, meeting_id, fingerprint="delayed-refund-alert"):
        return db.create_idea(
            db.Idea(
                meeting_id=meeting_id,
                title="Notify customers about delayed refunds",
                source_quote="refunds are silently delayed",
                speaker="Ana",
                timestamp="00:12:30",
                urgency="high",
                fingerprint=fingerprint,
            )
        )

    def make_attempt(self, idea_id, repo_id):
        return db.create_attempt(
            db.Attempt(idea_id=idea_id, repository_id=repo_id, repo_ref="abc123")
        )


class TestInit(DatabaseTestCase):
    def test_creates_all_tables(self):
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        names = {row["name"] for row in rows}
        self.assertTrue(
            {"repositories", "meetings", "ideas", "attempts", "friction_logs"}
            <= names
        )

    def test_is_idempotent(self):
        repo = self.make_repository()
        db.init_db()
        self.assertEqual(db.get_repository(repo.id).name, "acme-store")

    def test_foreign_keys_are_enforced(self):
        with self.assertRaises(sqlite3.IntegrityError):
            db.create_idea(db.Idea(meeting_id=999, title="orphan"))


class TestRepositories(DatabaseTestCase):
    def test_round_trip(self):
        created = self.make_repository()
        fetched = db.get_repository(created.id)
        self.assertEqual(fetched.name, "acme-store")
        self.assertEqual(fetched.source_type, db.RepoSource.DEMO)
        self.assertIsNone(fetched.catalog)
        self.assertIsNotNone(fetched.created_at)

    def test_catalog_survives_round_trip(self):
        repo = self.make_repository()
        catalog = db.ArchitectureCatalog(
            name="acme-store",
            language="python",
            framework="flask",
            internal_models=[db.ModelEntry(name="Order", fields=["id", "status"])],
            api_routes=[db.RouteEntry(method="GET", path="/orders")],
            external_integrations=[
                db.IntegrationEntry(name="Stripe", env_keys=["STRIPE_KEY"])
            ],
            codeowners={"payments/": "@team-payments"},
        )
        db.save_catalog(repo.id, catalog, source_ref="deadbeef")

        fetched = db.get_repository(repo.id)
        self.assertEqual(fetched.catalog.internal_models[0].fields, ["id", "status"])
        self.assertEqual(fetched.catalog.api_routes[0].path, "/orders")
        self.assertEqual(fetched.catalog.codeowners["payments/"], "@team-payments")
        self.assertEqual(fetched.source_ref, "deadbeef")
        self.assertIsNotNone(fetched.catalog_generated_at)

    def test_catalog_is_current_tracks_repo_ref(self):
        repo = self.make_repository()
        self.assertFalse(db.catalog_is_current(repo, "deadbeef"))

        db.save_catalog(repo.id, db.ArchitectureCatalog(), source_ref="deadbeef")
        onboarded = db.get_repository(repo.id)
        self.assertTrue(db.catalog_is_current(onboarded, "deadbeef"))
        self.assertFalse(db.catalog_is_current(onboarded, "newsha"))

    def test_get_or_create_does_not_duplicate(self):
        first = self.make_repository()
        again = db.get_or_create_repository(
            db.Repository(name="acme-store", source="/tmp/acme-store")
        )
        self.assertEqual(first.id, again.id)
        self.assertEqual(len(db.list_repositories()), 1)


class TestMeetings(DatabaseTestCase):
    def test_round_trip_with_minutes(self):
        meeting = self.make_meeting()
        meeting.minutes = db.MeetingMinutes(
            summary="Refund delays discussed.",
            key_points=["refund status lives in payments"],
            action_items=["check delay_reason field"],
        )
        db.update_meeting(meeting)

        fetched = db.get_meeting(meeting.id)
        self.assertEqual(fetched.external_source, db.MeetingSource.SEED)
        self.assertEqual(fetched.minutes.action_items, ["check delay_reason field"])

    def test_list(self):
        self.make_meeting()
        self.assertEqual(len(db.list_meetings()), 1)


class TestIdeas(DatabaseTestCase):
    def test_round_trip_preserves_attribution(self):
        meeting = self.make_meeting()
        idea = self.make_idea(meeting.id)

        fetched = db.get_idea(idea.id)
        self.assertEqual(fetched.speaker, "Ana")
        self.assertEqual(fetched.source_quote, "refunds are silently delayed")
        self.assertEqual(fetched.timestamp, "00:12:30")
        self.assertEqual(fetched.status, db.IdeaStatus.PENDING)

    def test_filter_by_status_and_meeting(self):
        meeting = self.make_meeting()
        first = self.make_idea(meeting.id)
        self.make_idea(meeting.id, fingerprint="other")
        db.set_idea_status(first.id, db.IdeaStatus.APPROVED)

        self.assertEqual(len(db.list_ideas(status=db.IdeaStatus.PENDING)), 1)
        self.assertEqual(len(db.list_ideas(status=db.IdeaStatus.APPROVED)), 1)
        self.assertEqual(len(db.list_ideas(meeting_id=meeting.id)), 2)

    def test_fingerprint_links_repeat_across_meetings(self):
        first_meeting = self.make_meeting()
        original = self.make_idea(first_meeting.id)

        second_meeting = self.make_meeting()
        match = db.find_idea_by_fingerprint("delayed-refund-alert")
        self.assertEqual(match.id, original.id)

        repeat = db.create_idea(
            db.Idea(
                meeting_id=second_meeting.id,
                title="Notify customers about delayed refunds",
                fingerprint="delayed-refund-alert",
                duplicate_of_id=match.id,
            )
        )
        self.assertEqual(db.get_idea(repeat.id).duplicate_of_id, original.id)

    def test_unknown_fingerprint_returns_none(self):
        self.assertIsNone(db.find_idea_by_fingerprint("nothing"))
        self.assertIsNone(db.find_idea_by_fingerprint(""))


class TestAttempts(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repository()
        self.meeting = self.make_meeting()
        self.idea = self.make_idea(self.meeting.id)

    def test_round_trip(self):
        attempt = self.make_attempt(self.idea.id, self.repo.id)
        fetched = db.get_attempt(attempt.id)
        self.assertEqual(fetched.status, db.AttemptStatus.QUEUED)
        self.assertEqual(fetched.repo_ref, "abc123")
        self.assertIsNone(fetched.plan)

    def test_plan_and_results_survive_round_trip(self):
        attempt = self.make_attempt(self.idea.id, self.repo.id)
        attempt.plan = db.TechnicalPlan(
            summary="Add delay detection",
            repo_changes=[
                db.PlanStep(order=1, action="modify", target="models/refund.py")
            ],
            external_requirements=["Twilio SMS"],
            mock_strategy="Generate MockSMSClient",
        )
        attempt.diff = "--- a/models/refund.py\n+++ b/models/refund.py"
        attempt.test_exit_code = 0
        attempt.test_stdout = "2 passed"
        db.update_attempt(attempt)

        fetched = db.get_attempt(attempt.id)
        self.assertEqual(fetched.plan.repo_changes[0].target, "models/refund.py")
        self.assertEqual(fetched.plan.external_requirements, ["Twilio SMS"])
        self.assertEqual(fetched.test_exit_code, 0)
        self.assertIn("refund.py", fetched.diff)

    def test_status_transitions_stamp_times(self):
        attempt = self.make_attempt(self.idea.id, self.repo.id)
        self.assertIsNone(db.get_attempt(attempt.id).started_at)

        db.set_attempt_status(attempt.id, db.AttemptStatus.PLANNING)
        started = db.get_attempt(attempt.id).started_at
        self.assertIsNotNone(started)
        self.assertIsNone(db.get_attempt(attempt.id).finished_at)

        db.set_attempt_status(attempt.id, db.AttemptStatus.CODING)
        self.assertEqual(db.get_attempt(attempt.id).started_at, started)

        db.set_attempt_status(attempt.id, db.AttemptStatus.COMPLETE)
        done = db.get_attempt(attempt.id)
        self.assertEqual(done.status, db.AttemptStatus.COMPLETE)
        self.assertEqual(done.started_at, started)
        self.assertIsNotNone(done.finished_at)

    def test_failure_records_error(self):
        attempt = self.make_attempt(self.idea.id, self.repo.id)
        db.set_attempt_status(attempt.id, db.AttemptStatus.FAILED, error="boom")
        fetched = db.get_attempt(attempt.id)
        self.assertEqual(fetched.error, "boom")
        self.assertIsNotNone(fetched.finished_at)

    def test_idea_can_have_multiple_attempts(self):
        self.make_attempt(self.idea.id, self.repo.id)
        self.make_attempt(self.idea.id, self.repo.id)
        self.assertEqual(len(db.list_attempts(idea_id=self.idea.id)), 2)


class TestFrictionLogs(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        repo = self.make_repository()
        meeting = self.make_meeting()
        idea = self.make_idea(meeting.id)
        self.attempt = self.make_attempt(idea.id, repo.id)

    def log(self, category, service, team):
        return db.create_friction_log(
            db.FrictionLog(
                attempt_id=self.attempt.id,
                category=category,
                service_name=service,
                owning_team=team,
                mock_implementation_path="mocks/mock_sms_client.py",
                required_action=f"Provision {service}",
                readiness_checklist=[
                    db.ReadinessItem(task=f"Acquire {service} key", owner=team)
                ],
            )
        )

    def test_round_trip_with_checklist(self):
        created = self.log(
            db.FrictionCategory.EXTERNAL_SERVICE_DEPENDENCY, "Twilio SMS", "@team-comms"
        )
        fetched = db.list_friction_logs(attempt_id=self.attempt.id)[0]
        self.assertEqual(fetched.id, created.id)
        self.assertEqual(fetched.category, db.FrictionCategory.EXTERNAL_SERVICE_DEPENDENCY)
        self.assertEqual(fetched.mock_implementation_path, "mocks/mock_sms_client.py")
        self.assertEqual(fetched.readiness_checklist[0].owner, "@team-comms")
        self.assertFalse(fetched.readiness_checklist[0].done)

    def test_aggregation_for_bottleneck_map(self):
        self.log(
            db.FrictionCategory.EXTERNAL_SERVICE_DEPENDENCY, "Twilio SMS", "@team-comms"
        )
        self.log(
            db.FrictionCategory.EXTERNAL_SERVICE_DEPENDENCY, "Stripe", "@team-payments"
        )
        self.log(
            db.FrictionCategory.AUTH_CREDENTIAL_REQUIRED, "Stripe", "@team-payments"
        )

        by_category = dict(db.count_friction_by("category"))
        self.assertEqual(by_category["EXTERNAL_SERVICE_DEPENDENCY"], 2)
        self.assertEqual(by_category["AUTH_CREDENTIAL_REQUIRED"], 1)

        by_team = db.count_friction_by("owning_team")
        self.assertEqual(by_team[0], ("@team-payments", 2))

        by_service = dict(db.count_friction_by("service_name"))
        self.assertEqual(by_service["Stripe"], 2)

    def test_aggregation_rejects_arbitrary_columns(self):
        with self.assertRaises(ValueError):
            db.count_friction_by("id; DROP TABLE friction_logs")

    def test_product_decision_category(self):
        created = self.log(
            db.FrictionCategory.PRODUCT_DECISION, "Refund policy", "@team-ops"
        )
        self.assertEqual(
            db.list_friction_logs()[0].category, db.FrictionCategory.PRODUCT_DECISION
        )
        self.assertEqual(created.category.value, "PRODUCT_DECISION")

    def test_orphan_log_is_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            db.create_friction_log(
                db.FrictionLog(
                    attempt_id=999,
                    category=db.FrictionCategory.CROSS_TEAM_CONTRACT,
                )
            )


if __name__ == "__main__":
    unittest.main()
