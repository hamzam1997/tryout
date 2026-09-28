"""Tests for GitHub OAuth endpoints."""

import tempfile
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
        self.client = flask_app.app.test_client()

    def tearDown(self):
        db.set_database_path(None)
        self._tmp.cleanup()

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
