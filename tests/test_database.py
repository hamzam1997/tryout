"""Production integration tests for database schema, models, and repositories."""

import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import database as db

FIXED_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


class DatabaseIntegrationTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        db.set_database_path(Path(self._tmp.name) / "test.db")
        db.init_db()

    def tearDown(self):
        db.set_database_path(None)
        self._tmp.cleanup()

    def test_schema_initialization_and_constraints(self):
        """Verify singular table names, schema idempotency, and foreign key cascades."""
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        tables = {row["name"] for row in rows}
        expected_singular = {"repository", "meeting", "idea", "attempt", "friction_log"}
        self.assertTrue(expected_singular <= tables, f"Expected singular tables, got: {tables}")

        # Idempotency check: re-running init_db preserves existing data
        repo = db.create_repository(db.Repository(name="acme", source="https://github.com/acme/store"))
        db.init_db()
        self.assertEqual(db.get_repository(repo.id).name, "acme")

        # Unique constraint on repository source
        with self.assertRaises((sqlite3.IntegrityError, db.IntegrityError)):
            db.create_repository(db.Repository(name="duplicate", source="https://github.com/acme/store"))

        # Foreign key integrity check: cannot create orphan idea
        with self.assertRaises((sqlite3.IntegrityError, db.IntegrityError)):
            db.create_idea(db.Idea(meeting_id=9999, title="orphan"))

        # Foreign key cascades
        meeting = db.create_meeting(db.Meeting(title="Sync", transcript="transcript"))
        idea1 = db.create_idea(db.Idea(meeting_id=meeting.id, title="Idea 1", idea_key="fp1"))
        idea2 = db.create_idea(
            db.Idea(meeting_id=meeting.id, title="Idea 2", original_idea_id=idea1.id)
        )
        attempt = db.create_attempt(db.Attempt(idea_id=idea1.id, repository_id=repo.id))
        db.create_friction_log(db.FrictionLog(attempt_id=attempt.id, category=db.FrictionCategory.PRODUCT_DECISION))

        # Deleting idea1 sets idea2.original_idea_id to NULL and cascades to attempt & friction_log
        with db.connect() as conn:
            conn.execute("DELETE FROM idea WHERE id = ?", (idea1.id,))
        self.assertIsNone(db.get_attempt(attempt.id))
        self.assertEqual(len(db.list_friction_logs(attempt_id=attempt.id)), 0)
        self.assertIsNone(db.get_idea(idea2.id).original_idea_id)

    def test_repository_and_architecture_catalog(self):
        """Verify repository operations and architecture catalog caching."""
        repo = db.get_or_create_repository(
            db.Repository(name="acme-store", source="/opt/acme", source_type=db.RepoSource.LOCAL)
        )
        # Idempotent get_or_create returns existing record
        same_repo = db.get_or_create_repository(
            db.Repository(name="acme-store", source="/opt/acme")
        )
        self.assertEqual(repo.id, same_repo.id)
        self.assertEqual(len(db.list_repositories()), 1)

        # Catalog persistence and freshness checking
        self.assertFalse(db.catalog_is_current(repo, "commit-sha-1"))
        catalog = db.ArchitectureCatalog(
            name="acme-store",
            language="python",
            framework="flask",
            internal_models=[db.ModelEntry(name="Order", fields=["id", "total"])],
            api_routes=[db.RouteEntry(method="GET", path="/orders", handler="list_orders")],
            external_integrations=[db.IntegrationEntry(name="Stripe", env_keys=["STRIPE_API_KEY"])],
            codeowners={"payments/": "@team-payments"},
        )
        db.save_catalog(repo.id, catalog, source_ref="commit-sha-1")
        updated = db.get_repository(repo.id)
        self.assertTrue(db.catalog_is_current(updated, "commit-sha-1"))
        self.assertFalse(db.catalog_is_current(updated, "commit-sha-2"))
        self.assertEqual(updated.catalog.api_routes[0].path, "/orders")
        self.assertEqual(updated.catalog.codeowners["payments/"], "@team-payments")

    def test_meeting_and_idea_deduplication(self):
        """Verify meeting storage, minutes, idea attribution, and cross-meeting deduplication."""
        meeting = db.create_meeting(
            db.Meeting(
                title="Sprint Kickoff",
                transcript="Alice: We need auto-refunds.",
                external_source=db.MeetingSource.SEED,
                minutes=db.MeetingMinutes(
                    summary="Auto-refunds discussed",
                    key_points=["Current refund flow is manual"],
                    action_items=["Automate refund webhook"],
                ),
            )
        )
        fetched_meeting = db.get_meeting(meeting.id)
        self.assertEqual(fetched_meeting.minutes.action_items, ["Automate refund webhook"])

        idea1 = db.create_idea(
            db.Idea(
                meeting_id=meeting.id,
                title="Automate refund webhook",
                speaker="Alice",
                cue_time="00:04:15",
                idea_key="refund-webhook-auto",
            )
        )
        idea2 = db.create_idea(db.Idea(meeting_id=meeting.id, title="Other feature", idea_key="other"))
        db.set_idea_status(idea1.id, db.IdeaStatus.APPROVED)

        self.assertEqual(len(db.list_ideas(status=db.IdeaStatus.APPROVED)), 1)
        self.assertEqual(len(db.list_ideas(meeting_id=meeting.id)), 2)

        # Cross-meeting duplicate matching via idea_key
        second_meeting = db.create_meeting(db.Meeting(title="Follow-up Sync", transcript="Alice: auto-refunds again."))
        matched_idea = db.find_idea_by_key("refund-webhook-auto")
        self.assertEqual(matched_idea.id, idea1.id)
        duplicate_idea = db.create_idea(
            db.Idea(
                meeting_id=second_meeting.id,
                title="Automate refund webhook",
                idea_key="refund-webhook-auto",
                original_idea_id=matched_idea.id,
            )
        )
        self.assertEqual(db.get_idea(duplicate_idea.id).original_idea_id, idea1.id)

        with_catalog = db.create_idea(
            db.Idea(
                meeting_id=meeting.id,
                title="Notify on delayed refunds",
                quote="automatically email the customer",
                cue_time="00:00:46",
                priority="high",
                attempt_hypothesis="Add refund status polling in routes/refunds.py",
                catalog_refs=["routes/refunds.py", "notifications-service"],
                idea_key="auto-notify-delayed-refunds",
            )
        )
        loaded = db.get_idea(with_catalog.id)
        self.assertEqual(loaded.catalog_refs, ["routes/refunds.py", "notifications-service"])
        self.assertEqual(loaded.attempt_hypothesis, "Add refund status polling in routes/refunds.py")

    def test_attempt_lifecycle_and_results(self):
        """Verify attempt execution state machine, execution timestamps, error recording, and plan diffs."""
        repo = db.create_repository(db.Repository(name="repo", source="/tmp/repo"))
        meeting = db.create_meeting(db.Meeting(title="Sync", transcript="transcript"))
        idea = db.create_idea(db.Idea(meeting_id=meeting.id, title="Idea"))

        attempt = db.create_attempt(db.Attempt(idea_id=idea.id, repository_id=repo.id, repo_ref="v1.0.0"))
        self.assertEqual(attempt.status, db.AttemptStatus.QUEUED)
        self.assertIsNone(attempt.started_at)
        self.assertIsNone(attempt.finished_at)

        # Transition to PLANNING stamps started_at
        db.set_attempt_status(attempt.id, db.AttemptStatus.PLANNING)
        attempt = db.get_attempt(attempt.id)
        started_at = attempt.started_at
        self.assertIsNotNone(started_at)

        # Saving plan, diff, and execution output
        attempt.plan = db.TechnicalPlan(
            summary="Implementation plan",
            repo_changes=[db.PlanStep(order=1, action="edit", target="app.py")],
        )
        attempt.diff = "@@ -1 +1 @@"
        attempt.test_exit_code = 0
        attempt.test_stdout = "All tests passed"
        db.update_attempt(attempt)

        # Transition to COMPLETE stamps finished_at and preserves started_at
        db.set_attempt_status(attempt.id, db.AttemptStatus.COMPLETE)
        done = db.get_attempt(attempt.id)
        self.assertEqual(done.status, db.AttemptStatus.COMPLETE)
        self.assertEqual(done.started_at, started_at)
        self.assertIsNotNone(done.finished_at)
        self.assertEqual(done.plan.repo_changes[0].target, "app.py")

        # Failure records error message and marks finished_at
        attempt2 = db.create_attempt(db.Attempt(idea_id=idea.id, repository_id=repo.id))
        db.set_attempt_status(attempt2.id, db.AttemptStatus.FAILED, error="SyntaxError")
        failed = db.get_attempt(attempt2.id)
        self.assertEqual(failed.error, "SyntaxError")
        self.assertIsNotNone(failed.finished_at)

    def test_friction_logs_and_bottleneck_aggregation(self):
        """Verify friction log tracking with checklist, safe aggregation, and injection protection."""
        repo = db.create_repository(db.Repository(name="repo", source="/tmp/repo2"))
        meeting = db.create_meeting(db.Meeting(title="Sync", transcript="transcript"))
        idea = db.create_idea(db.Idea(meeting_id=meeting.id, title="Idea"))
        attempt = db.create_attempt(db.Attempt(idea_id=idea.id, repository_id=repo.id))

        db.create_friction_log(
            db.FrictionLog(
                attempt_id=attempt.id,
                category=db.FrictionCategory.EXTERNAL_SERVICE_DEPENDENCY,
                service_name="Stripe",
                owning_team="@team-payments",
                readiness_checklist=[db.ReadinessItem(task="Get API key", owner="@team-payments", done=False)],
            )
        )
        db.create_friction_log(
            db.FrictionLog(
                attempt_id=attempt.id,
                category=db.FrictionCategory.AUTH_CREDENTIAL_REQUIRED,
                service_name="Stripe",
                owning_team="@team-payments",
            )
        )
        db.create_friction_log(
            db.FrictionLog(
                attempt_id=attempt.id,
                category=db.FrictionCategory.EXTERNAL_SERVICE_DEPENDENCY,
                service_name="Twilio",
                owning_team="@team-comms",
            )
        )

        logs = db.list_friction_logs(attempt_id=attempt.id)
        self.assertEqual(len(logs), 3)
        self.assertEqual(logs[0].readiness_checklist[0].task, "Get API key")

        # Bottleneck aggregations
        by_category = dict(db.count_friction_by("category"))
        self.assertEqual(by_category[db.FrictionCategory.EXTERNAL_SERVICE_DEPENDENCY.value], 2)
        self.assertEqual(by_category[db.FrictionCategory.AUTH_CREDENTIAL_REQUIRED.value], 1)

        by_service = dict(db.count_friction_by("service_name"))
        self.assertEqual(by_service["Stripe"], 2)
        self.assertEqual(by_service["Twilio"], 1)

        # Invalid column injection rejected
        with self.assertRaises(ValueError):
            db.count_friction_by("attempt_id; DROP TABLE friction_log")

    def test_sqlalchemy_orm_relationships(self):
        """Verify direct SQLAlchemy 2.0 ORM models, relationships, and session usage."""
        with db.session_scope() as session:
            repo = db.RepositoryModel(
                name="orm-repo", source="/tmp/orm-repo", source_type="local", created_at=FIXED_TIME
            )
            meeting = db.MeetingModel(
                title="ORM Design", transcript="Discussing ORM", created_at=FIXED_TIME
            )
            session.add_all([repo, meeting])
            session.flush()

            idea = db.IdeaModel(
                meeting_id=meeting.id,
                title="SQLAlchemy models",
                created_at=FIXED_TIME,
            )
            session.add(idea)
            session.flush()

            attempt = db.AttemptModel(
                idea_id=idea.id,
                repository_id=repo.id,
                status="PLANNING",
                created_at=FIXED_TIME,
            )
            session.add(attempt)
            session.flush()

            flog = db.FrictionLogModel(
                attempt_id=attempt.id,
                category="PRODUCT_DECISION",
                created_at=FIXED_TIME,
            )
            session.add(flog)

        # In a new session, verify relationships load seamlessly
        with db.session_scope() as session:
            loaded_meeting = session.get(db.MeetingModel, meeting.id)
            self.assertEqual(len(loaded_meeting.ideas), 1)
            self.assertEqual(loaded_meeting.ideas[0].title, "SQLAlchemy models")

            loaded_attempt = session.get(db.AttemptModel, attempt.id)
            self.assertEqual(loaded_attempt.repository.name, "orm-repo")
            self.assertEqual(loaded_attempt.idea.title, "SQLAlchemy models")
            self.assertEqual(len(loaded_attempt.friction_logs), 1)


if __name__ == "__main__":
    unittest.main()
