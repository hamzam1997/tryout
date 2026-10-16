"""The pull request description says what happened to the attempt's tests."""

import unittest

from agents.github_pr import pull_request_body


class TestPullRequestBody(unittest.TestCase):
    def test_reports_the_test_outcome(self):
        passed = pull_request_body("Expose refund state.", 3, 0)
        self.assertIn("## Summary\nExpose refund state.", passed)
        self.assertIn("Tests pass", passed)
        self.assertIn("approved idea #3", passed)
        self.assertNotIn("not executed", passed)

        self.assertIn("Tests fail (exit 1)", pull_request_body("s", 3, 1))
        self.assertIn("Tests were not run", pull_request_body("s", 3, None))


if __name__ == "__main__":
    unittest.main()
