"""Tests for repository onboarding and catalog endpoints."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import database as db

_BOOTSTRAP = tempfile.TemporaryDirectory()
db.set_database_path(Path(_BOOTSTRAP.name) / "bootstrap.db")

import app as flask_app  # noqa: E402
from schemas import (  # noqa: E402
    ArchitectureCatalog,
    ModuleDescription,
    RepoSource,
    Repository,
)

SAMPLE_CATALOG = ArchitectureCatalog(
    name="test-service",
    language="Python",
    framework="Flask",
    entrypoint="app.py",
    test_command="pytest",
    summary="A test service",
    modules=[
        ModuleDescription(
            name="Core",
            path="core/",
            description="Core logic",
            responsibilities=["processing"],
            key_files=["core/main.py"],
            owner="@team-core",
        )
    ],
    internal_models=[],
    api_routes=[],
    external_integrations=[],
    config_keys=[],
)


class RepositoriesViewTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        db.set_database_path(Path(self._tmp.name) / "test.db")
        db.init_db()
        self.client = flask_app.app.test_client()

    def tearDown(self):
        db.set_database_path(None)
        self._tmp.cleanup()

    def test_list_repositories_empty(self):
        resp = self.client.get("/repositories")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), [])

    @mock.patch("views.repositories.threading.Thread")
    def test_onboard_demo_repo_uses_github_demo(self, _thread):
        resp = self.client.post("/repositories/onboard", json={"source_type": "demo"})
        self.assertEqual(resp.status_code, 202)
        repo = resp.get_json()["repository"]
        self.assertEqual(repo["source_type"], "github")
        self.assertEqual(repo["source"], "https://github.com/hamzam1997/acme-store")

    @mock.patch("views.repositories.threading.Thread")
    @mock.patch("agents.git_utils.fetch_github_repository")
    @mock.patch("agents.repo_onboarder.RepoOnboarder.generate_catalog", return_value=SAMPLE_CATALOG)
    def test_onboard_github_repo(self, mock_gen, mock_fetch, mock_thread_cls):
        def run_sync(target=None, args=(), **kwargs):
            t = mock.MagicMock()
            t.start.side_effect = lambda: target(*args)
            return t

        mock_thread_cls.side_effect = run_sync

        # Create a dummy scanned directory for git fetch mock
        dummy_dir = Path(self._tmp.name) / "dummy_gh_repo"
        dummy_dir.mkdir()
        (dummy_dir / "app.py").write_text("print('hello')", encoding="utf-8")
        mock_fetch.return_value = (dummy_dir, "abc123sha", "org/payment-service")

        with self.client.session_transaction() as sess:
            sess["github_token"] = "fake-token"

        resp = self.client.post(
            "/repositories/onboard",
            json={"source_type": "github", "repo_full_name": "org/payment-service"},
        )
        self.assertEqual(resp.status_code, 202)
        data = resp.get_json()
        self.assertEqual(data["repository"]["source_type"], "github")
        self.assertEqual(data["repository"]["source"], "https://github.com/org/payment-service")

        # Retrieve catalog endpoint after sync completion
        repo_id = data["repository"]["id"]
        cat_resp = self.client.get(f"/repositories/{repo_id}/catalog")
        self.assertEqual(cat_resp.status_code, 200)
        self.assertEqual(cat_resp.get_json()["name"], "test-service")

    def test_onboard_invalid_source_type(self):
        resp = self.client.post("/repositories/onboard", json={"source_type": "bitbucket"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.get_json())

    def test_get_nonexistent_repository(self):
        resp = self.client.get("/repositories/9999")
        self.assertEqual(resp.status_code, 404)

    def test_delete_repository(self):
        # Create a repo
        repo = db.create_repository(
            Repository(
                name="to-delete",
                source="https://github.com/org/to-delete",
                source_type=RepoSource.GITHUB,
            )
        )
        self.assertIsNotNone(db.get_repository(repo.id))

        # Delete it via API
        resp = self.client.delete(f"/repositories/{repo.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["id"], repo.id)

        # Verify it's gone
        self.assertIsNone(db.get_repository(repo.id))

    def test_delete_nonexistent_repository(self):
        resp = self.client.delete("/repositories/9999")
        self.assertEqual(resp.status_code, 404)
