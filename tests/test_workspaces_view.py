import tempfile
import unittest
from pathlib import Path

import database as db
from app import app
from auth_helpers import login
from schemas import Meeting, WorkspaceRole


class TestWorkspacesView(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.set_database_path(Path(self.tmp.name) / "database")
        db.init_db()
        self.client = login(app.test_client(), uid="owner", name="Olu")
        self.home = db.current_workspace()

    def tearDown(self):
        db.set_database_path(None)
        self.tmp.cleanup()

    def test_create_switches_and_lists(self):
        created = self.client.post("/api/workspaces", json={"name": "Payments"}).get_json()
        body = self.client.get("/api/workspaces").get_json()
        self.assertEqual(body["current"], created["id"])
        self.assertEqual(sorted(w["name"] for w in body["workspaces"]), ["Olu's workspace", "Payments"])

        self.client.post(f"/api/workspaces/{self.home}/switch")
        self.assertEqual(self.client.get("/api/workspaces").get_json()["current"], self.home)

    def test_switching_to_a_workspace_you_are_not_in_is_404(self):
        other = db.create_workspace("Theirs", "someone-else")
        self.assertEqual(self.client.post(f"/api/workspaces/{other.id}/switch").status_code, 404)

    def test_only_the_owner_renames_or_deletes(self):
        db.add_member(self.home, "member", WorkspaceRole.MEMBER)
        member = app.test_client()
        with member.session_transaction() as sess:
            sess["user"] = {"uid": "member"}
        self.assertEqual(member.patch(f"/api/workspaces/{self.home}", json={"name": "x"}).status_code, 403)
        self.assertEqual(member.delete(f"/api/workspaces/{self.home}").status_code, 403)

        self.assertEqual(self.client.patch(f"/api/workspaces/{self.home}", json={"name": "Ops"}).status_code, 200)
        self.assertEqual(db.get_workspace(self.home).name, "Ops")

    def test_delete_removes_records_and_memberships(self):
        db.create_meeting(Meeting(title="m", transcript="t"))
        self.assertEqual(self.client.delete(f"/api/workspaces/{self.home}").status_code, 204)
        self.assertIsNone(db.get_workspace(self.home))
        self.assertEqual(db.list_memberships(workspace_id=self.home), [])
        db.set_workspace(None)
        self.assertEqual(db.list_meetings(), [])


if __name__ == "__main__":
    unittest.main()
