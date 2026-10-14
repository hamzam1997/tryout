import tempfile
import unittest
from pathlib import Path

import database as db
from app import app
from auth_helpers import login
from schemas import Meeting, WorkspaceRole


def as_user(uid, workspace_id):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = {"uid": uid}
        sess["workspace_id"] = workspace_id
    return client


class TestMembersAndRoles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.set_database_path(Path(self.tmp.name) / "database")
        db.init_db()
        self.owner = login(app.test_client(), uid="owner")
        self.ws = db.current_workspace()
        db.add_member(self.ws, "admin", WorkspaceRole.ADMIN)
        db.add_member(self.ws, "member", WorkspaceRole.MEMBER)
        self.admin = as_user("admin", self.ws)
        self.member = as_user("member", self.ws)
        self.meeting = db.create_meeting(Meeting(title="m", transcript="t"))

    def tearDown(self):
        db.set_database_path(None)
        self.tmp.cleanup()

    def test_members_read_but_cannot_change_repos_or_meetings(self):
        self.assertEqual(self.member.get("/api/meetings").status_code, 200)
        self.assertEqual(self.member.delete(f"/api/meetings/{self.meeting.id}").status_code, 403)
        self.assertEqual(self.member.post("/api/repositories/onboard", json={}).status_code, 403)
        self.assertEqual(self.member.delete("/api/ideas/1").status_code, 403)
        self.assertEqual(self.admin.delete(f"/api/meetings/{self.meeting.id}").status_code, 204)

    def test_member_list_shows_roles(self):
        members = self.member.get(f"/api/workspaces/{self.ws}/members").get_json()
        self.assertEqual({m["uid"]: m["role"] for m in members}, {"owner": "owner", "admin": "admin", "member": "member"})
        self.assertEqual([m["uid"] for m in members if m["you"]], ["member"])

    def test_role_changes_follow_the_rules(self):
        url = f"/api/workspaces/{self.ws}/members"
        self.assertEqual(self.member.patch(f"{url}/admin", json={"role": "member"}).status_code, 403)
        self.assertEqual(self.admin.patch(f"{url}/member", json={"role": "admin"}).status_code, 200)
        self.assertEqual(self.admin.patch(f"{url}/member", json={"role": "owner"}).status_code, 403)
        self.assertEqual(self.admin.patch(f"{url}/owner", json={"role": "member"}).status_code, 403)
        self.assertEqual(self.owner.patch(f"{url}/owner", json={"role": "admin"}).status_code, 409)  # last owner
        self.assertEqual(self.owner.patch(f"{url}/admin", json={"role": "owner"}).status_code, 200)
        self.assertEqual(self.owner.patch(f"{url}/owner", json={"role": "admin"}).status_code, 200)

    def test_leave_and_remove(self):
        url = f"/api/workspaces/{self.ws}/members"
        self.assertEqual(self.owner.delete(f"{url}/owner").status_code, 409)  # last owner cannot leave
        self.assertEqual(self.admin.delete(f"{url}/owner").status_code, 403)
        self.assertEqual(self.member.delete(f"{url}/admin").status_code, 403)
        self.assertEqual(self.member.delete(f"{url}/member").status_code, 204)  # leave
        self.assertIsNone(db.get_membership(self.ws, "member"))

    def test_removed_member_loses_access_immediately(self):
        self.assertEqual(len(self.member.get("/api/meetings").get_json()), 1)
        self.assertEqual(self.admin.delete(f"/api/workspaces/{self.ws}/members/member").status_code, 204)
        self.assertEqual(self.member.get("/api/meetings").get_json(), [])  # back in their own workspace
        self.assertEqual(
            self.member.get("/api/meetings", headers={"X-Workspace-Id": str(self.ws)}).status_code, 403
        )


if __name__ == "__main__":
    unittest.main()
