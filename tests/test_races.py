"""Concurrent requests that used to duplicate records."""

import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import database as db
from app import app
from auth_helpers import login
from config import settings
from database import client as db_client
from views import auth


class RaceTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.set_database_path(Path(self.tmp.name) / "database")
        db.init_db()

    def tearDown(self):
        db.set_database_path(None)
        self.tmp.cleanup()

    def test_parallel_first_requests_create_one_personal_workspace(self):
        user = {"uid": "new", "email": "n@x.com"}
        results = []
        with mock.patch.object(settings, "seed_demo_data", False):
            threads = [
                threading.Thread(target=lambda: results.append(auth._create_personal_workspace(user)))
                for _ in range(8)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        self.assertEqual(len(db.list_memberships(uid="new")), 1)
        self.assertEqual({m.workspace_id for m in results}, {db.list_memberships(uid="new")[0].workspace_id})

    def test_an_idea_being_started_rejects_a_second_start(self):
        client = login(app.test_client())
        self.assertTrue(db.claim("idea-attempt:1"))
        self.assertEqual(client.post("/api/ideas/1/approve").status_code, 409)
        db.release("idea-attempt:1")
        self.assertEqual(client.post("/api/ideas/1/approve").status_code, 404)  # lock is free again

    def test_a_dead_holders_lock_expires(self):
        self.assertTrue(db.claim("k"))
        self.assertFalse(db.claim("k"))
        with mock.patch.object(db_client, "LOCK_TTL_SECONDS", 0):
            self.assertTrue(db.claim("k"))


if __name__ == "__main__":
    unittest.main()
