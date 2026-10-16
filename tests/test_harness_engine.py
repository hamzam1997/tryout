"""The coding agent loop answers each tool call the way Gemini 3+ expects."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from google.genai import types

import database as db
from agents.harness.engine import AttemptHarness
from schemas import ArchitectureCatalog, Attempt, Idea


def _reply(*calls: types.FunctionCall):
    content = types.Content(role="model", parts=[types.Part(function_call=c) for c in calls])
    return SimpleNamespace(function_calls=list(calls), candidates=[SimpleNamespace(content=content)])


class TestHarnessToolLoop(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        db.set_database_path(Path(self.temp.name) / "database")
        db.init_db()
        self.workspace = Path(self.temp.name) / "repo"
        self.workspace.mkdir()
        (self.workspace / "app.py").write_text("print('hi')\n")
        subprocess.run(["git", "init", "-q"], cwd=self.workspace, check=True)

    def tearDown(self):
        db.set_database_path(None)
        self.temp.cleanup()

    def test_tool_results_carry_the_call_id(self):
        client = MagicMock()
        client.models.generate_content.side_effect = [
            _reply(types.FunctionCall(id="call-7", name="list_directory", args={"path": "."})),
            _reply(types.FunctionCall(id="call-8", name="complete_attempt", args={
                "summary": "Looked around.", "pr_title": "Explore", "testing_notes": "None",
            })),
        ]
        attempt = db.create_attempt(Attempt(idea_id=1, repository_id=1))
        with patch("agents.harness.engine.get_client", return_value=client):
            harness = AttemptHarness(
                workspace=self.workspace,
                catalog=ArchitectureCatalog(name="repo"),
                idea=Idea(meeting_id=1, title="Explore"),
                attempt=attempt,
            )
            result = harness.run()

        self.assertTrue(result.success)
        # Our answer to call-7 is in the history, matched by id and name.
        history = client.models.generate_content.call_args_list[1].kwargs["contents"]
        answers = [p.function_response for c in history for p in c.parts if p.function_response]
        self.assertEqual(len(answers), 1)
        response = answers[0]
        self.assertEqual((response.id, response.name), ("call-7", "list_directory"))
        self.assertIn("app.py", response.response["result"])
        # No sampling overrides: Gemini 3+ guidance is to leave temperature unset.
        config = client.models.generate_content.call_args_list[0].kwargs["config"]
        self.assertIsNone(config.temperature)


if __name__ == "__main__":
    unittest.main()
