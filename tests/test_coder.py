"""Fallback behavior for incomplete coding-model output."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.attempt_agent import FileChangeBatch
from agents.coder import CodingAgent
from schemas import ArchitectureCatalog, Idea, TechnicalPlan


class TestCodingAgentFallbacks(unittest.TestCase):
    def test_external_requirement_missing_mock_gets_runnable_fallback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch("agents.coder.generate_changes", return_value=FileChangeBatch()):
                batch, diff = CodingAgent("test-model").generate_and_apply(
                    root=root,
                    idea=Idea(meeting_id=1, title="Notify", description="Send a notification"),
                    plan=TechnicalPlan(
                        summary="Add notifications", external_requirements=["notifications-service"]
                    ),
                    catalog=ArchitectureCatalog(name="Demo"),
                    source_context="",
                )

            paths = {change.path for change in batch.changes}
            self.assertIn("mock_external_service.py", paths)
            self.assertIn("test_prototype.py", paths)
            self.assertIn("MockExternalService", (root / "mock_external_service.py").read_text())
            self.assertIn("send_notification", (root / "test_prototype.py").read_text())
            self.assertIn("mock_external_service.py", diff)
            self.assertIn("test_prototype.py", diff)


if __name__ == "__main__":
    unittest.main()
