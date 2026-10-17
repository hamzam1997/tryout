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
from agents.harness.engine import MAX_STEPS, UNTESTED_NOTE, AttemptHarness
from runner.sandbox import SandboxResult
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
        # Like a cloned repo: existing files are committed, so only agent changes show in the diff.
        subprocess.run(["git", "add", "-A"], cwd=self.workspace, check=True)
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "files"],
            cwd=self.workspace, check=True,
        )

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
        # Every result tells the agent its remaining budget.
        self.assertEqual(response.response["steps_left"], MAX_STEPS - 1)
        self.assertNotIn("budget_note", response.response)

    def _run(self, replies, max_steps=None):
        client = MagicMock()
        client.models.generate_content.side_effect = replies
        attempt = db.create_attempt(Attempt(idea_id=1, repository_id=1))
        with patch("agents.harness.engine.get_client", return_value=client), \
                patch("agents.harness.engine.run_tests",
                      return_value=SandboxResult(exit_code=0, stdout="OK", stderr="")):
            harness = AttemptHarness(
                workspace=self.workspace, catalog=ArchitectureCatalog(name="repo"),
                idea=Idea(meeting_id=1, title="Explore"), attempt=attempt,
            )
            if max_steps:
                harness.max_steps = max_steps
            return harness.run(), client, attempt

    def test_low_budget_tells_the_agent_to_finish(self):
        ls = types.FunctionCall(id="c", name="list_directory", args={"path": "."})
        _, client, _ = self._run([_reply(ls), _reply(ls), _reply(ls)], max_steps=3)
        history = client.models.generate_content.call_args_list[-1].kwargs["contents"]
        notes = [p.function_response.response.get("budget_note")
                 for c in history for p in c.parts if p.function_response]
        self.assertIn("Only 2 steps left", notes[0])
        self.assertIn("Last step: call complete_attempt now", notes[1])

    def test_edits_after_the_last_test_run_are_retested_before_reporting(self):
        result, _, attempt = self._run([
            _reply(types.FunctionCall(id="t", name="run_tests", args={"command": "true"})),
            _reply(types.FunctionCall(id="e", name="create_file", args={"path": "new.py", "content": "x = 1\n"})),
            _reply(types.FunctionCall(id="d", name="complete_attempt", args={"summary": "s", "pr_title": "t"})),
        ])
        # The stale pre-edit result is replaced by a fresh run of the same command.
        self.assertEqual(result.test_exit_code, 0)
        self.assertNotEqual(result.test_output, UNTESTED_NOTE)
        reruns = [e for e in attempt.events if e.action == "run_tests" and "final code" in e.detail]
        self.assertEqual(len(reruns), 1)

    def test_timeout_keeps_the_work_and_says_what_is_missing(self):
        result, _, attempt = self._run([
            _reply(types.FunctionCall(id="e", name="create_file", args={"path": "new.py", "content": "x = 1\n"})),
            _reply(types.FunctionCall(id="t", name="run_tests", args={"command": "true"})),
        ], max_steps=2)
        self.assertFalse(result.success)
        self.assertIn("2-step budget", result.summary)
        self.assertIn("1 files: new.py", result.summary)
        self.assertEqual(result.testing_notes, "The last test run passed.")
        self.assertEqual(result.test_exit_code, 0)
        self.assertEqual(attempt.events[-1].action, "timeout")


if __name__ == "__main__":
    unittest.main()
