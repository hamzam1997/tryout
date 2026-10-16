"""The technical planner grounds a plan in the catalog and keeps external work separate."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from agents.planner import generate_plan, plan_markdown
from schemas import ArchitectureCatalog, Idea, Meeting, PlanStep, TechnicalPlan

PLAN = TechnicalPlan(
    summary="Flag refunds pending over 5 days and notify the customer.",
    repo_changes=[
        PlanStep(order=1, action="modify", target="routes/refunds.py", rationale="Add delay check"),
        PlanStep(order=2, action="create", target="tests/test_delayed.py", rationale="Cover it"),
    ],
    external_requirements=["notifications-service (team-messaging)"],
    mock_strategy="Stub the notifications client and assert it was called.",
)


class TestPlanner(unittest.TestCase):
    def setUp(self):
        self.idea = Idea(
            meeting_id=1,
            title="Delayed refund alert",
            description="Tell customers when a refund is late.",
            quote="Can we tell people when refunds are stuck?",
            attempt_hypothesis="Extend refunds routes; mock notifications.",
            catalog_refs=["routes/refunds.py", "notifications-service"],
        )
        self.meeting = Meeting(title="Weekly ops", transcript="Marco: refunds are stuck.")
        self.catalog = ArchitectureCatalog(name="acme-store")

    def _plan_with(self, response):
        client = MagicMock()
        client.models.generate_content.return_value = response
        with patch("agents.planner.get_client", return_value=client):
            plan = generate_plan(self.idea, self.meeting, self.catalog, "planning-model")
        return plan, client.models.generate_content.call_args.kwargs

    def test_requests_a_structured_plan_grounded_in_idea_and_meeting(self):
        plan, call = self._plan_with(SimpleNamespace(parsed=PLAN, text=None))

        self.assertEqual(plan, PLAN)
        self.assertEqual(call["model"], "planning-model")
        self.assertIs(call["config"].response_schema, TechnicalPlan)
        self.assertEqual(call["config"].response_mime_type, "application/json")
        for evidence in ("Delayed refund alert", "Weekly ops", "refunds are stuck",
                         "Can we tell people when refunds are stuck?", "notifications-service"):
            self.assertIn(evidence, call["contents"])
        # The model is told to keep in-repo changes and external requirements apart.
        self.assertIn("external_requirements", call["config"].system_instruction)

    def test_falls_back_to_json_text_when_sdk_does_not_parse(self):
        plan, _ = self._plan_with(SimpleNamespace(parsed=None, text=PLAN.model_dump_json()))
        self.assertEqual(plan, PLAN)

    def test_empty_response_raises(self):
        with self.assertRaises(RuntimeError):
            self._plan_with(SimpleNamespace(parsed=None, text=""))

    def test_markdown_separates_repo_changes_from_external_requirements(self):
        text = plan_markdown(PLAN)
        self.assertIn("1. modify `routes/refunds.py`: Add delay check", text)
        self.assertIn("External requirements (mock each one):\n- notifications-service", text)
        self.assertIn("Mock strategy: Stub the notifications client", text)
        self.assertIn("- none", plan_markdown(TechnicalPlan(summary="Local only")))


if __name__ == "__main__":
    unittest.main()
