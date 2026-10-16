"""The coding agent's workspace search tool."""

import tempfile
import unittest
from pathlib import Path

from agents.harness.tools import search_code


class TestSearchCode(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name)
        (self.workspace / "routes.py").write_text("def cancel_order():\n    status = '-cancelled'\n")

    def tearDown(self):
        self._tmp.cleanup()

    def test_finds_matches_with_file_and_line(self):
        self.assertIn("routes.py:1:def cancel_order", search_code(self.workspace, "cancel_order"))

    def test_reports_no_matches(self):
        self.assertEqual(search_code(self.workspace, "refund_webhook"), "No matches found.")

    def test_query_starting_with_dash_is_a_pattern(self):
        self.assertIn("routes.py:2:", search_code(self.workspace, "-cancelled"))


if __name__ == "__main__":
    unittest.main()
