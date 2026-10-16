import tempfile
import unittest
from pathlib import Path

import database as db
from seed_history import seed_friction_history


class TestSeedHistory(unittest.TestCase):
    def test_seed_populates_analytics_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            db.set_database_path(Path(tmp) / "database")
            db.init_db()
            self.assertTrue(seed_friction_history())
            self.assertFalse(seed_friction_history())  # idempotent
            self.assertEqual(len(db.list_friction_logs()), 8)
            self.assertEqual(dict(db.count_friction_by("service_name"))["Stripe"], 2)
            # Seeded reports read as finished: tests ran, mocks are in the diff, times are set.
            for attempt in db.list_attempts():
                self.assertEqual(attempt.status, db.AttemptStatus.COMPLETE)
                self.assertEqual(attempt.test_exit_code, 0)
                self.assertIsNotNone(attempt.finished_at)
                mocks = {log.mock_implementation_path for log in db.list_friction_logs(attempt_id=attempt.id)} - {""}
                for path in mocks:
                    self.assertEqual(attempt.diff.count(f"diff --git a/{path} b/{path}\n"), 1)
            db.set_database_path(None)


if __name__ == "__main__":
    unittest.main()
