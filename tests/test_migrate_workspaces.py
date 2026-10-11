import tempfile
import unittest
from pathlib import Path

import database as db
from database.migrate_workspaces import migrate
from schemas import Idea, Meeting


class TestMigrateWorkspaces(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.set_database_path(Path(self.tmp.name) / "database")
        db.init_db()

    def tearDown(self):
        db.set_database_path(None)
        self.tmp.cleanup()

    def test_moves_legacy_records_once_and_owner_can_see_them(self):
        db.upsert_user(uid="u1", email="owner@x.com", name="Owner")
        meeting = db.create_meeting(Meeting(title="old", transcript="t"))
        db.create_idea(Idea(meeting_id=meeting.id, title="old idea"))

        workspace_id, moved = migrate("owner@x.com")
        self.assertEqual(moved, 2)
        self.assertEqual(db.get_membership(workspace_id, "u1").role.value, "owner")
        db.set_workspace(workspace_id)
        self.assertEqual([m.title for m in db.list_meetings()], ["old"])

        db.set_workspace(None)
        self.assertEqual(migrate("owner@x.com")[1], 0)  # already migrated

    def test_unknown_owner_stops(self):
        with self.assertRaises(SystemExit):
            migrate("nobody@x.com")


if __name__ == "__main__":
    unittest.main()
