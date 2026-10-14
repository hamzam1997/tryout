import tempfile
import unittest
from pathlib import Path
from unittest import mock

import database as db
from app import app
from auth_helpers import login
from database.client import get_firestore_client
from config import settings
from schemas import ArchitectureCatalog, Idea, IdeaStatus, Meeting, RepoSource, Repository, WorkspaceRole


def github_user(login_name="octo"):
    return mock.Mock(status_code=200, json=lambda: {"login": login_name, "name": login_name})


def github_token(token="gho_secret"):
    return mock.Mock(status_code=200, json=lambda: {"access_token": token}, raise_for_status=lambda: None)


class TestWorkspaceGitHub(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.set_database_path(Path(self.tmp.name) / "database")
        db.init_db()
        self.admin = login(app.test_client(), uid="admin")
        self.ws = db.current_workspace()

    def tearDown(self):
        db.set_database_path(None)
        self.tmp.cleanup()

    def _connect(self, client=None, token="gho_secret"):
        """The Connect GitHub button: OAuth login for this workspace, then the callback."""
        client = client or self.admin
        with mock.patch.object(settings, "github_client_id", "id"), mock.patch.object(settings, "github_client_secret", "s"):
            client.get(f"/api/auth/github/login?workspace={self.ws}")
        with client.session_transaction() as sess:
            state = sess["oauth_state"]
        with mock.patch("views.auth.requests.post", return_value=github_token(token)), mock.patch(
            "views.auth.requests.get", return_value=github_user()
        ):
            resp = client.get(f"/api/auth/github/callback?code=c&state={state}")
        db.set_workspace(self.ws)  # public endpoints clear the request's workspace
        return resp

    def test_connect_stores_the_token_encrypted_and_never_returns_it(self):
        self.assertIn("github_connected=1", self._connect().headers["Location"])
        body = self.admin.get(f"/api/workspaces/{self.ws}/github").get_json()
        self.assertEqual((body["connected"], body["login"]), (True, "octo"))
        raw = get_firestore_client().collection("workspace_github").document(str(self.ws)).get().to_dict()
        self.assertNotIn("gho_secret", str(raw))
        self.assertEqual(db.get_github_token(self.ws), "gho_secret")
        self.assertNotIn("token", self.admin.get(f"/api/workspaces/{self.ws}/github").get_json())

    def test_connecting_keeps_the_signed_in_identity(self):
        self._connect()
        with self.admin.session_transaction() as sess:
            self.assertEqual(sess["user"]["uid"], "admin")  # not "github:octo"
        self.assertEqual(db.list_memberships(uid="github:octo"), [])

    def test_members_cannot_connect(self):
        db.add_member(self.ws, "m", WorkspaceRole.MEMBER)
        member = app.test_client()
        with member.session_transaction() as sess:
            sess["user"] = {"uid": "m"}
            sess["workspace_id"] = self.ws
        self.assertIn("auth_error", self._connect(member, token="gho_member").headers["Location"])
        self.assertIsNone(db.get_github_token(self.ws))

    def test_any_members_approval_uses_the_workspace_connection(self):
        self._connect()
        meeting = db.create_meeting(Meeting(title="m", transcript="t"))
        idea = db.create_idea(Idea(meeting_id=meeting.id, title="i", status=IdeaStatus.PENDING))
        repo = db.create_repository(Repository(
            name="r", source=self.tmp.name, source_type=RepoSource.LOCAL,
            catalog=ArchitectureCatalog(name="r"), catalog_status="ready",
        ))
        db.add_member(self.ws, "m", WorkspaceRole.MEMBER)
        member = app.test_client()  # never signed in with GitHub
        with member.session_transaction() as sess:
            sess["user"] = {"uid": "m"}
            sess["workspace_id"] = self.ws
        with mock.patch("views.ideas.queue_attempt") as queue_attempt:
            resp = member.post(f"/api/ideas/{idea.id}/approve", json={"repository_id": repo.id})
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(queue_attempt.call_args.args[1], "gho_secret")

    def test_disconnect(self):
        self._connect()
        self.assertEqual(self.admin.delete(f"/api/workspaces/{self.ws}/github").status_code, 204)
        self.assertFalse(self.admin.get(f"/api/workspaces/{self.ws}/github").get_json()["connected"])
        self.assertIsNone(db.get_github_token(self.ws))


if __name__ == "__main__":
    unittest.main()
