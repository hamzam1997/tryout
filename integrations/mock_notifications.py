"""Mock adapter for notifications-service and Slack attempt completion alerts.

Mocks the following external integrations:
1. notifications-service (@team-comms): Downstream notification routing and delivery.
2. Slack API / Bot Integration: Workspace OAuth bot token (SLACK_BOT_TOKEN) and chat.postMessage API.
3. Target Slack Channel Routing: Configured alert destination (SLACK_CHANNEL).
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from schemas import Attempt, FrictionLog, Idea


class MockNotificationsService:
    """Mock notification client simulating Slack and notifications-service.

    Records dispatched notifications in memory and returns realistic delivery responses
    without connecting to external networks or requiring real Slack credentials.
    """

    def __init__(
        self,
        bot_token: str | None = None,
        default_channel: str | None = None,
        service_url: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.bot_token = bot_token or os.environ.get("SLACK_BOT_TOKEN", "xoxb-mock-bot-token")
        self.default_channel = default_channel or os.environ.get("SLACK_CHANNEL", "#tryout-attempts")
        self.service_url = service_url or os.environ.get(
            "NOTIFICATIONS_SERVICE_URL", "https://notifications-service.internal"
        )
        self.base_url = (base_url or os.environ.get("APP_BASE_URL", "http://localhost:8080")).rstrip("/")
        self.recorded_calls: list[dict[str, Any]] = []

    @property
    def sent_notifications(self) -> list[dict[str, Any]]:
        """List of all delivered notifications for test inspection."""
        return self.recorded_calls

    @property
    def last_notification(self) -> dict[str, Any] | None:
        """The most recently recorded notification payload or None."""
        return self.recorded_calls[-1] if self.recorded_calls else None

    def clear(self) -> None:
        """Reset the recorded calls queue."""
        self.recorded_calls.clear()

    def build_report_url(self, attempt_id: int) -> str:
        """Construct the web report URL for an attempt."""
        return f"{self.base_url}/attempts/{attempt_id}"

    def summarize_friction_blockers(
        self, friction_logs: list[FrictionLog] | None
    ) -> list[dict[str, Any]]:
        """Extract structured summary items from FrictionLog records."""
        summaries: list[dict[str, Any]] = []
        for log in friction_logs or []:
            category_val = (
                log.category.value if hasattr(log.category, "value") else str(log.category)
            )
            summaries.append({
                "id": log.id,
                "category": category_val,
                "service_name": log.service_name or "General",
                "owning_team": log.owning_team or "Unassigned",
                "required_action": log.required_action or "Review blocker",
                "mock_implementation_path": log.mock_implementation_path or "",
                "readiness_checklist": list(log.readiness_checklist or []),
                "summary": (
                    f"[{category_val}] {log.service_name or 'General'}: "
                    f"{log.required_action or 'Action needed'} "
                    f"({log.owning_team or 'Unassigned'})"
                ),
            })
        return summaries

    def build_payload(
        self,
        attempt: Attempt,
        idea: Idea | None = None,
        friction_logs: list[FrictionLog] | None = None,
        channel: str | None = None,
    ) -> dict[str, Any]:
        """Construct the full notification payload including text and Slack blocks."""
        target_channel = channel or self.default_channel
        report_url = self.build_report_url(attempt.id)
        idea_title = idea.title if idea else f"Idea #{attempt.idea_id}"
        status_str = (
            attempt.status.value if hasattr(attempt.status, "value") else str(attempt.status)
        )
        blocker_summaries = self.summarize_friction_blockers(friction_logs)

        # Slack mrkdwn fallback text
        lines = [
            f"🎯 *Attempt #{attempt.id} Completed*",
            f"*Idea:* {idea_title}",
            f"*Status:* `{status_str}`",
            f"*Report:* {report_url}",
        ]
        if attempt.pull_request_url:
            lines.append(f"*Pull Request:* {attempt.pull_request_url}")

        if blocker_summaries:
            lines.append(f"\n*Friction Blockers ({len(blocker_summaries)}):*")
            for b in blocker_summaries:
                lines.append(f"• *[{b['category']}]* {b['service_name']}: {b['required_action']} (Team: {b['owning_team']})")
        else:
            lines.append("\n*Friction Blockers:* None detected")

        text_message = "\n".join(lines)

        # Slack Block Kit structure
        blocks: list[dict[str, Any]] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Attempt #{attempt.id} Finished: {idea_title[:60]}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Status:*\n`{status_str}`"},
                    {"type": "mrkdwn", "text": f"*Blockers:*\n{len(blocker_summaries)} recorded"},
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Report URL:* <{report_url}|View Attempt #{attempt.id} Report>",
                },
            },
        ]

        if attempt.pull_request_url:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Pull Request:* <{attempt.pull_request_url}|GitHub PR>",
                },
            })

        if blocker_summaries:
            blocker_text_items = [
                f"• *[{b['category']}]* *{b['service_name']}*: {b['required_action']} _(Owner: {b['owning_team']})_"
                for b in blocker_summaries
            ]
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Friction & Blockers Found:*\n" + "\n".join(blocker_text_items),
                },
            })
        else:
            blocks.append({
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": "✅ No operational or architectural blockers identified."}
                ],
            })

        return {
            "channel": target_channel,
            "attempt_id": attempt.id,
            "idea_id": attempt.idea_id,
            "idea_title": idea_title,
            "status": status_str,
            "report_url": report_url,
            "pull_request_url": attempt.pull_request_url,
            "blocker_count": len(blocker_summaries),
            "blockers": blocker_summaries,
            "text": text_message,
            "blocks": blocks,
        }

    def post_message(
        self,
        channel: str | None = None,
        text: str = "",
        blocks: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Low-level dispatch simulating Slack chat.postMessage."""
        target_channel = channel or self.default_channel
        notification_id = f"notif_{uuid.uuid4().hex[:12]}"
        timestamp = f"{int(time.time())}.{uuid.uuid4().hex[:6]}"

        response_payload = {
            "ok": True,
            "notification_id": notification_id,
            "channel": target_channel,
            "ts": timestamp,
            "status": "delivered",
            "delivered_at": datetime.now(timezone.utc).isoformat(),
            "message": {
                "type": "message",
                "subtype": "bot_message",
                "text": text,
                "blocks": blocks or [],
                "ts": timestamp,
                "bot_id": "B_TRYOUT_BOT",
            },
            "metadata": metadata or {},
        }
        self.recorded_calls.append(response_payload)
        return response_payload

    def send_attempt_notification(
        self,
        attempt: Attempt,
        idea: Idea | None = None,
        friction_logs: list[FrictionLog] | None = None,
        channel: str | None = None,
    ) -> dict[str, Any]:
        """Format and dispatch attempt completion notification to Slack."""
        payload = self.build_payload(
            attempt=attempt,
            idea=idea,
            friction_logs=friction_logs,
            channel=channel,
        )
        response = self.post_message(
            channel=payload["channel"],
            text=payload["text"],
            blocks=payload["blocks"],
            metadata=payload,
        )
        return response


# Aliases for flexible naming across modules and tests
MockNotificationsClient = MockNotificationsService
NotificationsAdapter = MockNotificationsService
