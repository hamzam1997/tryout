"""Evaluator sign-in: a throwaway account with a seeded workspace, no Google or GitHub."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import database as db

_BOOTSTRAP = tempfile.TemporaryDirectory()
db.set_database_path(Path(_BOOTSTRAP.name) / "bootstrap.db")

import app as flask_app  # noqa: E402
from schemas import ArchitectureCatalog, Idea, IdeaStatus, Meeting, RepoSource, Repository  # noqa: E402


class EvaluatorLoginTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        db.set_database_path(Path(self._tmp.name) / "test.db")
        db.init_db()
        self.client = flask_app.app.test_client()
        enabled = mock.patch("views.auth.settings.evaluator_login", True)
        enabled.start()
        self.addCleanup(enabled.stop)

    def tearDown(self):
        db.set_database_path(None)
        self._tmp.cleanup()

    def test_disabled_by_default(self):
        with mock.patch("views.auth.settings.evaluator_login", False):
            self.assertEqual(self.client.post("/api/auth/evaluator").status_code, 404)
            self.assertFalse(self.client.get("/api/auth/firebase-config").get_json()["evaluatorLogin"])

    def test_config_tells_the_landing_page_to_offer_it(self):
        self.assertTrue(self.client.get("/api/auth/firebase-config").get_json()["evaluatorLogin"])

    def test_creates_a_signed_in_evaluator_with_an_empty_workspace(self):
        with mock.patch("views.auth.settings.seed_demo_data", True):  # as on the live deploy
            resp = self.client.post("/api/auth/evaluator")
        self.assertEqual(resp.status_code, 200)
        user = resp.get_json()["user"]
        self.assertTrue(user["uid"].startswith("evaluator-"))
        self.assertEqual(user["provider"], "evaluator")
        # Plain names for judges; uniqueness lives in the uid.
        self.assertEqual(user["name"], "Evaluator")
        names = [w["name"] for w in self.client.get("/api/workspaces").get_json()["workspaces"]]
        self.assertEqual(names, ["Evaluator's workspace"])

        me = self.client.get("/api/auth/me").get_json()
        self.assertEqual(me["user"]["uid"], user["uid"])
        self.assertEqual(me["user"]["provider"], "evaluator")
        # Signed in for the whole API, in a workspace of their own that starts empty,
        # even where other new workspaces get demo history.
        self.assertEqual(self.client.get("/api/meetings").get_json(), [])
        self.assertEqual(self.client.get("/api/repositories").get_json(), [])
        self.assertEqual(self.client.get("/api/bottlenecks").get_json()["total"], 0)
        memberships = db.list_memberships(uid=user["uid"])
        self.assertEqual(len(memberships), 1)
        self.assertEqual(resp.get_json()["workspace_id"], memberships[0].workspace_id)

    def test_every_sign_in_starts_from_scratch(self):
        first = self.client.post("/api/auth/evaluator").get_json()
        db.set_workspace(first["workspace_id"])
        db.create_meeting(Meeting(title="Judge's meeting", transcript="t"))
        self.assertEqual(len(self.client.get("/api/meetings").get_json()), 1)
        second = self.client.post("/api/auth/evaluator").get_json()
        self.assertNotEqual(first["user"]["uid"], second["user"]["uid"])
        self.assertNotEqual(first["workspace_id"], second["workspace_id"])
        self.assertEqual(self.client.get("/api/meetings").get_json(), [])

    @mock.patch("requests.get")
    @mock.patch("requests.post")
    def test_connecting_github_keeps_the_evaluator_and_workspace(self, mock_post, mock_get):
        """The onboarding card sends evaluators through the server OAuth flow."""
        mock_post.return_value.json.return_value = {"access_token": "gho_judge"}
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"login": "judge", "name": "A Judge"}
        login = self.client.post("/api/auth/evaluator").get_json()

        with mock.patch("views.auth.settings.github_client_id", "id"), \
                mock.patch("views.auth.settings.github_client_secret", "secret"):
            start = self.client.get("/api/auth/github/login")
            self.assertEqual(start.status_code, 302)
            with self.client.session_transaction() as sess:
                state = sess["oauth_state"]
            done = self.client.get(f"/api/auth/github/callback?state={state}&code=c")
        self.assertIn("auth_success=1", done.headers["Location"])

        # Still the same evaluator in the same workspace, now with GitHub repo access.
        me = self.client.get("/api/auth/me").get_json()["user"]
        self.assertEqual(me["uid"], login["user"]["uid"])
        self.assertEqual(db.list_memberships(uid=me["uid"])[0].workspace_id, login["workspace_id"])
        status = self.client.get("/api/auth/github/status").get_json()
        self.assertTrue(status["authenticated"])
        self.assertEqual(status["user"]["login"], "judge")

    def test_logout_ends_the_evaluator_session(self):
        self.client.post("/api/auth/evaluator")
        self.client.post("/api/auth/logout")
        self.assertEqual(self.client.get("/api/meetings").status_code, 401)


class DemoTokenTestCase(unittest.TestCase):
    """Attempts on the demo repo fall back to the server's demo token, nothing else does."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        db.set_database_path(Path(self._tmp.name) / "test.db")
        db.init_db()
        self.client = flask_app.app.test_client()
        with mock.patch("views.auth.settings.evaluator_login", True):
            login = self.client.post("/api/auth/evaluator").get_json()
        db.set_workspace(login["workspace_id"])  # test data goes in the evaluator's workspace
        meeting = db.create_meeting(Meeting(title="Sync", transcript="t"))
        self.ideas = [
            db.create_idea(Idea(meeting_id=meeting.id, title=f"Idea {i}", idea_key=f"k{i}",
                                status=IdeaStatus.PENDING))
            for i in range(2)
        ]

    def tearDown(self):
        db.set_database_path(None)
        self._tmp.cleanup()

    def _repo(self, source):
        return db.create_repository(Repository(
            name=source.rsplit("/", 1)[-1], source=source, source_type=RepoSource.GITHUB,
            catalog=ArchitectureCatalog(name="r"), catalog_status="ready",
        ))

    def _approve_token(self, idea, repo):
        with mock.patch("views.ideas.settings.demo_github_token", "demo-token"), \
                mock.patch("views.ideas.queue_attempt") as queue_attempt:
            resp = self.client.post(f"/api/ideas/{idea.id}/approve", json={"repository_id": repo.id})
        self.assertEqual(resp.status_code, 202)
        return queue_attempt.call_args.args[1]

    def test_demo_repo_uses_the_demo_token(self):
        repo = self._repo("https://github.com/hamzam1997/acme-store")
        self.assertEqual(self._approve_token(self.ideas[0], repo), "demo-token")

    def test_other_repos_never_get_it(self):
        repo = self._repo("https://github.com/someone/else")
        self.assertIsNone(self._approve_token(self.ideas[1], repo))

    def test_the_users_own_token_wins(self):
        repo = self._repo("https://github.com/hamzam1997/acme-store")
        with self.client.session_transaction() as sess:
            sess["github_token"] = "user-token"
        self.assertEqual(self._approve_token(self.ideas[0], repo), "user-token")


if __name__ == "__main__":
    unittest.main()
