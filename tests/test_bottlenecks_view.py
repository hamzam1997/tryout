import tempfile
import unittest
from pathlib import Path

import database as db
from auth_helpers import login
from app import app
from seed_history import seed_friction_history


class TestBottlenecksView(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.set_database_path(Path(self.tmp.name) / "database")
        db.init_db()
        self.client = login(app.test_client())

    def tearDown(self):
        db.set_database_path(None)
        self.tmp.cleanup()

    def test_empty_map(self):
        body = self.client.get("/api/bottlenecks").get_json()
        self.assertEqual((body["total"], body["logs"], body["weeks_saved"]), (0, [], 0))

    def test_seeded_map_aggregates(self):
        seed_friction_history()
        body = self.client.get("/api/bottlenecks").get_json()
        self.assertEqual(body["total"], 8)
        self.assertEqual(body["attempts"], 4)
        self.assertEqual(body["by_service"][0], {"name": "Stripe", "count": 2})
        self.assertNotIn("unknown", [t["name"] for t in body["by_team"]])
        self.assertTrue(all(r["idea_title"] for r in body["logs"]))
        self.assertGreater(body["weeks_saved"], 0)


if __name__ == "__main__":
    unittest.main()
