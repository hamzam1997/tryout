import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from runner import sandbox


class TestSandbox(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_reports_exit_code_and_output(self):
        result = sandbox.run("echo hi; echo oops >&2; exit 3", self.workspace)
        self.assertEqual((result.exit_code, result.stdout, result.stderr), (3, "hi\n", "oops\n"))
        self.assertIn("Exit code: 3", result.to_text())

    def test_runs_in_workspace_without_server_secrets(self):
        with patch.dict(os.environ, {"GITHUB_CLIENT_SECRET": "s3cret"}):
            result = sandbox.run("pwd; env", self.workspace)
        self.assertEqual(result.exit_code, 0)
        self.assertIn(self.workspace.resolve().name, result.stdout)
        self.assertNotIn("s3cret", result.stdout)
        self.assertNotIn(f"HOME={self.workspace}", result.stdout)

    def test_timeout_kills_the_command(self):
        with patch.object(sandbox.settings, "execution_timeout_seconds", 1):
            start = time.monotonic()
            result = sandbox.run("sleep 30", self.workspace)
        self.assertTrue(result.timed_out)
        self.assertLess(time.monotonic() - start, 5)
        self.assertIn("timed out", result.to_text())


if __name__ == "__main__":
    unittest.main()
