"""Seed historical attempts + friction logs so analytics are never empty on first launch."""

from __future__ import annotations

import logging

import database as db
from schemas import (
    Attempt, AttemptStatus, FrictionCategory as C, FrictionLog, Idea, IdeaStatus,
    Meeting, MeetingSource, MeetingStatus, ReadinessItem as R, IdeasExtractStatus,
)

logger = logging.getLogger(__name__)

SEED_ID = "seed-friction-history"
EXT, AUTH, SCHEMA, TEAM, PROD = (
    C.EXTERNAL_SERVICE_DEPENDENCY, C.AUTH_CREDENTIAL_REQUIRED,
    C.SCHEMA_MIGRATION_REQUIRED, C.CROSS_TEAM_CONTRACT, C.PRODUCT_DECISION,
)

# (idea title, [(category, service, owner, mock file, action, [(task, owner)])])
HISTORY = [
    ("Auto-retry failed payments", [
        (EXT, "Stripe", "@team-payments", "integrations/mock_stripe_webhooks.py",
         "Expose a payment_failed webhook endpoint in staging.",
         [("Register payment_failed webhook in Stripe dashboard", "@team-payments")]),
        (AUTH, "Stripe", "@team-payments", "integrations/mock_stripe_webhooks.py",
         "Issue a restricted API key and webhook signing secret.",
         [("Create STRIPE_WEBHOOK_SECRET for staging", "@team-payments")]),
    ]),
    ("SMS order status updates", [
        (AUTH, "Twilio", "@team-comms", "integrations/mock_twilio_client.py",
         "Request the Messaging scope for the staging Twilio subaccount.",
         [("Grant SMS scope to subaccount", "@team-comms"), ("Add TWILIO_AUTH_TOKEN to Secret Manager", "@team-platform")]),
        (SCHEMA, "acme-store", "@team-platform", "",
         "Add a phone_number column to customers.",
         [("Write and review customers.phone_number migration", "@team-platform")]),
    ]),
    ("Weekly digest email for store managers", [
        (AUTH, "SendGrid", "@team-comms", "integrations/mock_sendgrid_client.py",
         "Provision a SendGrid API key with mail.send for staging.",
         [("Create SENDGRID_API_KEY", "@team-comms")]),
        (PROD, "digest-content", "unknown", "",
         "Decide which metrics belong in the digest.",
         [("Product to define digest metrics", "Product Manager")]),
    ]),
    ("Customer alert for delayed refunds", [
        (EXT, "notifications-service", "@team-comms", "integrations/mock_notifications_client.py",
         "Expose a send-notification endpoint other teams can call.",
         [("Publish staging endpoint and API docs", "@team-comms")]),
        (TEAM, "refund-status API", "@team-payments", "",
         "Add a delayed_reason field to the refund record.",
         [("Agree on refund status contract", "@team-payments")]),
    ]),
]


def seed_friction_history() -> bool:
    """Create the historical data once. Returns True if it was created."""
    if any(m.external_id == SEED_ID for m in db.list_meetings()):
        return False
    meeting = db.create_meeting(Meeting(
        title="Q3 Platform Planning (Historical)", external_source=MeetingSource.SEED,
        external_id=SEED_ID, transcript="Historical planning notes (seeded).",
        status=MeetingStatus.PROCESSED, ideas_status=IdeasExtractStatus.PROCESSED,
    ))
    for title, blockers in HISTORY:
        idea = db.create_idea(Idea(meeting_id=meeting.id, title=title, status=IdeaStatus.DONE))
        attempt = db.create_attempt(Attempt(
            idea_id=idea.id, repository_id=0, status=AttemptStatus.COMPLETE,
        ))
        for cat, svc, owner, mock, action, tasks in blockers:
            db.create_friction_log(FrictionLog(
                attempt_id=attempt.id, category=cat, service_name=svc, owning_team=owner,
                mock_implementation_path=mock, required_action=action,
                readiness_checklist=[R(task=t, owner=o) for t, o in tasks],
            ))
    return True


if __name__ == "__main__":  # python seed_history.py <workspace_id>
    import sys

    db.init_db()
    db.set_workspace(int(sys.argv[1]))
    print("seeded" if seed_friction_history() else "already seeded")
