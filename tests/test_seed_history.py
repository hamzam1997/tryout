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
            db.set_database_path(None)


if __name__ == "__main__":
    unittest.main()
