"""Tests for GitHub OAuth endpoints."""

import tempfile
from auth_helpers import login
import unittest
from pathlib import Path
from unittest import mock

import database as db

_BOOTSTRAP = tempfile.TemporaryDirectory()
db.set_database_path(Path(_BOOTSTRAP.name) / "bootstrap.db")

import app as flask_app  # noqa: E402
from config import settings  # noqa: E402


class AuthViewTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        db.set_database_path(Path(self._tmp.name) / "test.db")
        db.init_db()
        self.client = login(flask_app.app.test_client())

    def tearDown(self):
        db.set_database_path(None)
        self._tmp.cleanup()

    def test_firebase_sync_sets_a_persistent_session_cookie(self):
        with mock.patch("views.auth.db.upsert_user", return_value=None), mock.patch(
            "views.auth._verify_id_token", return_value={"uid": "u1", "email": "a@x.com"}
        ):
            resp = self.client.post("/api/auth/firebase-sync", json={"id_token": "tok"})
        cookie = resp.headers.get("Set-Cookie", "")
        self.assertIn("Expires=", cookie)  # not a browser-session cookie
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)

    def test_firebase_sync_rejects_a_missing_or_invalid_token(self):
        client = flask_app.app.test_client()
        with mock.patch("views.auth._verify_id_token", side_effect=ValueError("bad token")):
            resp = client.post("/api/auth/firebase-sync", json={"user": {"uid": "admin"}})
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(client.get("/api/ideas").status_code, 401)  # no session was created

    def test_firebase_sync_takes_identity_from_the_token_not_the_body(self):
        client = flask_app.app.test_client()
        with mock.patch("views.auth.db.upsert_user", return_value=None), mock.patch(
            "views.auth._verify_id_token", return_value={"uid": "real", "email": "r@x.com"}
        ):
            client.post("/api/auth/firebase-sync", json={"id_token": "tok", "user": {"uid": "forged"}})
        with client.session_transaction() as sess:
            self.assertEqual(sess["user"]["uid"], "real")

    def test_api_requires_sign_in_but_login_endpoints_do_not(self):
        client = flask_app.app.test_client()
        for path in ("/api/ideas", "/api/meetings", "/api/repositories", "/api/bottlenecks", "/api/attempts/1"):
            self.assertEqual(client.get(path).status_code, 401, path)
        self.assertEqual(client.get("/api/auth/firebase-config").status_code, 200)
        self.assertEqual(client.get("/health").status_code, 200)

    def test_github_status_unconfigured(self):
        with mock.patch.object(settings, "github_client_id", ""):
            resp = self.client.get("/api/auth/github/status")
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertFalse(data["configured"])
            self.assertFalse(data["authenticated"])

    def test_github_login_unconfigured(self):
        with mock.patch.object(settings, "github_client_id", ""):
            resp = self.client.get("/api/auth/github/login")
            self.assertEqual(resp.status_code, 503)

    def test_github_login_redirect(self):
        with mock.patch.object(settings, "github_client_id", "test-client-id"), \
             mock.patch.object(settings, "github_client_secret", "test-client-secret"):
            resp = self.client.get("/api/auth/github/login")
            self.assertEqual(resp.status_code, 302)
            self.assertIn("https://github.com/login/oauth/authorize", resp.headers["Location"])
            self.assertIn("test-client-id", resp.headers["Location"])

    def test_github_callback_state_mismatch(self):
        with self.client.session_transaction() as sess:
            sess["oauth_state"] = "valid-state"

        resp = self.client.get("/api/auth/github/callback?state=wrong-state&code=test-code")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("auth_error", resp.headers["Location"])

    @mock.patch("requests.get")
    @mock.patch("requests.post")
    def test_github_callback_success(self, mock_post, mock_get):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "gho_test123"}
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "login": "octocat",
            "name": "Mona Lisa",
            "avatar_url": "https://example.com/avatar.png",
        }

        with self.client.session_transaction() as sess:
            sess["oauth_state"] = "valid-state"

        with mock.patch.object(settings, "github_client_id", "test-id"), \
             mock.patch.object(settings, "github_client_secret", "test-secret"):
            resp = self.client.get("/api/auth/github/callback?state=valid-state&code=test-code")
            self.assertEqual(resp.status_code, 302)
            self.assertIn("auth_success=1", resp.headers["Location"])

            # Verify status now reports authenticated
            status_resp = self.client.get("/api/auth/github/status")
            self.assertEqual(status_resp.status_code, 200)
            status_data = status_resp.get_json()
            self.assertTrue(status_data["authenticated"])
            self.assertEqual(status_data["user"]["login"], "octocat")

    def test_github_repos_unauthorized(self):
        resp = self.client.get("/api/auth/github/repos")
        self.assertEqual(resp.status_code, 401)

    @mock.patch("requests.get")
    def test_github_repos_success(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [
            {
                "id": 12345,
                "name": "cool-repo",
                "full_name": "octocat/cool-repo",
                "private": True,
                "description": "A private repo",
                "default_branch": "main",
                "html_url": "https://github.com/octocat/cool-repo",
                "updated_at": "2026-09-28T12:00:00Z",
            }
        ]
        with self.client.session_transaction() as sess:
            sess["github_token"] = "valid-token"

        resp = self.client.get("/api/auth/github/repos")
        self.assertEqual(resp.status_code, 200)
        repos = resp.get_json()
        self.assertEqual(len(repos), 1)
        self.assertEqual(repos[0]["full_name"], "octocat/cool-repo")
        self.assertTrue(repos[0]["private"])
