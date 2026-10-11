"""User A must never see or change workspace B's records through the API."""

import tempfile
import unittest
from pathlib import Path

import database as db
from app import app
from auth_helpers import login
from schemas import Attempt, FrictionCategory, FrictionLog, Idea, Meeting, Repository


class TestWorkspaceIsolation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.set_database_path(Path(self.tmp.name) / "database")
        db.init_db()
        # B's workspace and data
        self.b = login(app.test_client(), uid="b", name="B")
        meeting = db.create_meeting(Meeting(title="B sync", transcript="secret plans"))
        self.idea = db.create_idea(Idea(meeting_id=meeting.id, title="B idea"))
        repo = db.create_repository(Repository(name="b-repo", source="/tmp/b"))
        self.attempt = db.create_attempt(Attempt(idea_id=self.idea.id, repository_id=repo.id))
        db.create_friction_log(FrictionLog(
            attempt_id=self.attempt.id, category=FrictionCategory.PRODUCT_DECISION, service_name="b-svc",
        ))
        self.meeting, self.repo = meeting, repo
        # A, in a separate workspace
        self.a = login(app.test_client(), uid="a", name="A")

    def tearDown(self):
        db.set_database_path(None)
        self.tmp.cleanup()

    def test_lists_are_empty_for_another_workspace(self):
        for path in ("/api/meetings", "/api/ideas?status=ALL", "/api/repositories"):
            self.assertEqual(self.a.get(path).get_json(), [], path)
        self.assertEqual(self.a.get("/api/bottlenecks").get_json()["total"], 0)

    def test_records_of_another_workspace_are_404(self):
        for path in (f"/api/meetings/{self.meeting.id}", f"/api/ideas/{self.idea.id}",
                     f"/api/repositories/{self.repo.id}", f"/api/attempts/{self.attempt.id}"):
            self.assertEqual(self.a.get(path).status_code, 404, path)
        self.assertEqual(self.a.delete(f"/api/ideas/{self.idea.id}").status_code, 404)
        self.assertEqual(self.a.delete(f"/api/meetings/{self.meeting.id}").status_code, 404)

    def test_owner_still_sees_their_data(self):
        self.assertEqual(len(self.b.get("/api/meetings").get_json()), 1)
        self.assertEqual(self.b.get("/api/bottlenecks").get_json()["total"], 1)

    def test_asking_for_a_foreign_workspace_is_403(self):
        b_workspace = db.list_memberships(uid="b")[0].workspace_id
        resp = self.a.get("/api/meetings", headers={"X-Workspace-Id": str(b_workspace)})
        self.assertEqual(resp.status_code, 403)

    def test_new_user_gets_a_personal_workspace(self):
        client = app.test_client()
        with client.session_transaction() as sess:
            sess["user"] = {"uid": "new", "name": "Nia"}
        self.assertEqual(client.get("/api/meetings").get_json(), [])
        [membership] = db.list_memberships(uid="new")
        self.assertEqual(membership.role.value, "owner")
        self.assertEqual(db.get_workspace(membership.workspace_id).name, "Nia's workspace")


if __name__ == "__main__":
    unittest.main()
