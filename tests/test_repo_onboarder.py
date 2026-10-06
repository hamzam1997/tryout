"""Unit and integration tests for RepoOnboarder agent and architecture catalog generation."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from agents.repo_onboarder import (
    REPO_ONBOARDER_SYSTEM_INSTRUCTION,
    RepoOnboarder,
    compute_source_ref,
    extract_codeowners_from_skeleton,
    generate_architecture_catalog,
    onboard_repository,
)
from config import BASE_DIR
import database as db
from repo_scanner import scan_repo
from schemas import (
    ArchitectureCatalog,
    FileCategory,
    FileRole,
    IntegrationEntry,
    ModelEntry,
    ModuleDescription,
    RepoSkeleton,
    RepoSource,
    Repository,
    RouteEntry,
    ScannedFile,
)


class TestRepoOnboarder(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        db.set_database_path(Path(self._tmp.name) / "test.db")
        db.init_db()

        # Reusable sample catalog
        self.sample_catalog = ArchitectureCatalog(
            name="acme_store",
            language="Python",
            framework="Flask",
            entrypoint="app.py",
            test_command="python -m unittest discover -s tests",
            summary="E-commerce store backend handling orders, refunds, and payments.",
            dependencies=["Flask==3.0.3"],
            modules=[
                ModuleDescription(
                    name="Orders & Checkout",
                    path="routes/orders.py",
                    description="Order creation, checkout processing, and listing",
                    responsibilities=["Order listing", "Checkout flow"],
                    key_files=["routes/orders.py", "routes/checkout.py"],
                    owner="@team-orders",
                ),
                ModuleDescription(
                    name="Payments & Refunds",
                    path="routes/refunds.py",
                    description="Payment processing and refunds via external gateway",
                    responsibilities=["Charge authorization", "Refund processing"],
                    key_files=["routes/refunds.py", "integrations/payments_gateway.py"],
                    owner="@team-payments",
                ),
            ],
            key_files=[
                FileRole(path="app.py", role="Application entrypoint", owner="@team-platform"),
                FileRole(path="models.py", role="Core dataclasses", owner="@team-platform"),
                FileRole(path="routes/orders.py", role="Order management endpoints", owner="@team-orders"),
            ],
            internal_models=[
                ModelEntry(name="Customer", file_path="models.py", fields=["id", "name", "email"]),
                ModelEntry(name="Order", file_path="models.py", fields=["id", "customer_id", "total", "status"]),
                ModelEntry(name="Refund", file_path="models.py", fields=["id", "order_id", "amount", "reason"]),
            ],
            api_routes=[
                RouteEntry(method="GET", path="/orders", handler="list_orders", file_path="routes/orders.py"),
                RouteEntry(method="POST", path="/checkout", handler="create_order", file_path="routes/checkout.py"),
                RouteEntry(method="POST", path="/refunds", handler="process_refund", file_path="routes/refunds.py"),
            ],
            external_integrations=[
                IntegrationEntry(
                    name="PaymentsGateway",
                    file_path="integrations/payments_gateway.py",
                    auth="API Key",
                    env_keys=["PAYMENTS_API_KEY", "PAYMENTS_API_BASE"],
                )
            ],
            external_dependencies=["notifications-service (@team-comms)"],
            config_keys=["PORT", "FLASK_DEBUG", "PAYMENTS_API_KEY", "PAYMENTS_API_BASE"],
            codeowners={
                "/models.py": "@team-platform",
                "/routes/orders.py": "@team-orders",
                "/routes/checkout.py": "@team-payments",
                "/routes/refunds.py": "@team-payments",
                "/integrations/": "@team-payments",
            },
            coding_guidelines=["Run tests with python -m unittest discover -s tests"],
        )

    def tearDown(self):
        db.set_database_path(None)
        self._tmp.cleanup()

    def _create_mock_client(self, catalog: ArchitectureCatalog | None = None, wrap_markdown: bool = False):
        """Create a mock genai.Client returning a structured JSON response."""
        cat = catalog or self.sample_catalog
        text_payload = cat.model_dump_json()
        if wrap_markdown:
            text_payload = f"```json\n{text_payload}\n```"

        mock_response = MagicMock()
        mock_response.text = text_payload

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        return mock_client

    def test_architecture_catalog_schema(self):
        """Verify ArchitectureCatalog fields, defaults, and config_keys/config_schema synchronization."""
        catalog = ArchitectureCatalog(
            framework="FastAPI",
            config_keys=["ENV_A", "ENV_B"],
        )
        self.assertEqual(catalog.framework, "FastAPI")
        self.assertEqual(catalog.config_keys, ["ENV_A", "ENV_B"])
        # config_schema is synced for backward compatibility
        self.assertEqual(catalog.config_schema, ["ENV_A", "ENV_B"])

        # Vice-versa: populating config_schema syncs to config_keys
        legacy_catalog = ArchitectureCatalog(
            config_schema=["LEGACY_KEY"],
        )
        self.assertEqual(legacy_catalog.config_keys, ["LEGACY_KEY"])

    def test_compute_source_ref_stability(self):
        """Verify compute_source_ref produces consistent, non-empty hashes."""
        ref1 = compute_source_ref(BASE_DIR / "demo_repo" / "acme_store")
        ref2 = compute_source_ref(BASE_DIR / "demo_repo" / "acme_store")
        self.assertEqual(ref1, ref2)
        self.assertTrue(len(ref1) > 0)

    def test_extract_codeowners_from_skeleton(self):
        """Verify CODEOWNERS parsing from skeleton configs."""
        skeleton = RepoSkeleton(
            repo_name="sample",
            files=[
                ScannedFile(
                    path="CODEOWNERS",
                    category=FileCategory.CONFIG,
                    content=(
                        "# Owners file\n"
                        "/models.py @team-platform\n"
                        "/routes/ @team-api\n"
                        "\n"
                        "# comments ignored\n"
                    ),
                )
            ],
        )
        owners = extract_codeowners_from_skeleton(skeleton)
        self.assertEqual(owners["/models.py"], "@team-platform")
        self.assertEqual(owners["/routes/"], "@team-api")

    def test_generate_catalog_with_mock_client(self):
        """Verify RepoOnboarder.generate_catalog formats prompt and parses response."""
        mock_client = self._create_mock_client(wrap_markdown=True)
        onboarder = RepoOnboarder(client=mock_client)

        skeleton = RepoSkeleton(
            repo_name="acme_store",
            context_string="Context of acme store",
        )

        catalog = onboarder.generate_catalog(skeleton)

        # Verify Gemini client called with correct arguments
        mock_client.models.generate_content.assert_called_once()
        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        self.assertEqual(call_kwargs["model"], "gemini-3.5-flash")
        self.assertIn("Context of acme store", call_kwargs["contents"])
        self.assertEqual(call_kwargs["config"].system_instruction, REPO_ONBOARDER_SYSTEM_INSTRUCTION)
        self.assertEqual(call_kwargs["config"].response_mime_type, "application/json")
        self.assertEqual(call_kwargs["config"].response_schema, ArchitectureCatalog)

        # Verify parsed catalog contents
        self.assertEqual(catalog.name, "acme_store")
        self.assertEqual(catalog.framework, "Flask")
        self.assertEqual(len(catalog.internal_models), 3)
        self.assertEqual(catalog.internal_models[0].name, "Customer")
        self.assertEqual(catalog.internal_models[0].fields, ["id", "name", "email"])
        self.assertEqual(len(catalog.api_routes), 3)
        self.assertEqual(catalog.api_routes[0].path, "/orders")
        self.assertEqual(len(catalog.external_integrations), 1)
        self.assertEqual(catalog.external_integrations[0].name, "PaymentsGateway")
        self.assertIn("PAYMENTS_API_KEY", catalog.config_keys)
        self.assertEqual(catalog.codeowners["/models.py"], "@team-platform")

    def test_generate_catalog_empty_response_raises(self):
        """Verify error raised when Gemini returns empty or null response."""
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = MagicMock(text="")
        onboarder = RepoOnboarder(client=mock_client)
        skeleton = RepoSkeleton(repo_name="test", context_string="test")

        with self.assertRaises(ValueError):
            onboarder.generate_catalog(skeleton)

    def test_onboard_by_path_and_database_persistence(self):
        """Verify onboard persists catalog into SQLite linked to repository."""
        mock_client = self._create_mock_client()
        onboarder = RepoOnboarder(client=mock_client)

        acme_dir = BASE_DIR / "demo_repo" / "acme_store"
        repo, catalog = onboarder.onboard(acme_dir, return_repo=True)

        # Verify DB record exists and is linked
        self.assertIsNotNone(repo.id)
        self.assertEqual(repo.name, "acme_store")
        self.assertIsNotNone(repo.catalog)
        self.assertEqual(repo.catalog.framework, "Flask")

        # Verify DB read
        fetched = db.get_repository(repo.id)
        self.assertIsNotNone(fetched)
        self.assertIsNotNone(fetched.catalog)
        self.assertEqual(fetched.catalog.name, "acme_store")
        self.assertEqual(len(fetched.catalog.internal_models), 3)
        self.assertEqual(len(fetched.catalog.api_routes), 3)
        self.assertEqual(len(fetched.catalog.external_integrations), 1)
        self.assertIn("PAYMENTS_API_KEY", fetched.catalog.config_keys)
        self.assertEqual(fetched.catalog.codeowners["/routes/orders.py"], "@team-orders")

    def test_caching_and_subsequent_idea_attempts(self):
        """Verify one-time caching: subsequent idea attempts reuse saved catalog without Gemini calls."""
        mock_client = self._create_mock_client()
        onboarder = RepoOnboarder(client=mock_client)

        acme_dir = BASE_DIR / "demo_repo" / "acme_store"

        # 1. Initial onboarding: Gemini called once
        catalog1 = onboarder.onboard(acme_dir)
        self.assertEqual(mock_client.models.generate_content.call_count, 1)

        # Fetch the persisted repository
        repo = db.get_repository_by_source(str(acme_dir.resolve()))
        self.assertIsNotNone(repo)

        # 2. Subsequent onboard call for the same repo (by ID or path) reuses cache
        catalog2 = onboarder.onboard(repo.id)
        self.assertEqual(mock_client.models.generate_content.call_count, 1)  # NOT incremented!
        self.assertEqual(catalog2.framework, catalog1.framework)

        catalog3 = onboarder.onboard(acme_dir)
        self.assertEqual(mock_client.models.generate_content.call_count, 1)  # Still NOT incremented!
        self.assertEqual(catalog3.name, catalog1.name)

        # 3. Simulate subsequent idea attempt using the cached catalog
        meeting = db.create_meeting(db.Meeting(title="Sprint Meeting", transcript="Automate refunds"))
        idea = db.create_idea(db.Idea(meeting_id=meeting.id, title="Auto-refund delayed orders"))
        attempt = db.create_attempt(db.Attempt(idea_id=idea.id, repository_id=repo.id))

        # Attempt accesses the repository's catalog
        attempt_repo = db.get_repository(attempt.repository_id)
        self.assertIsNotNone(attempt_repo.catalog)
        self.assertEqual(attempt_repo.catalog.framework, "Flask")
        self.assertEqual(mock_client.models.generate_content.call_count, 1)

        # Attempt uses onboarder.onboard(attempt.repository_id)
        attempt_catalog = onboarder.onboard(attempt.repository_id)
        self.assertEqual(attempt_catalog.summary, catalog1.summary)
        self.assertEqual(mock_client.models.generate_content.call_count, 1)

        # 4. Force refresh triggers a fresh Gemini generation
        catalog_refreshed = onboarder.onboard(repo.id, force_refresh=True)
        self.assertEqual(mock_client.models.generate_content.call_count, 2)
        self.assertEqual(catalog_refreshed.name, "acme_store")

    def test_convenience_functions(self):
        """Verify onboard_repository and generate_architecture_catalog functions."""
        mock_client = self._create_mock_client()
        skeleton = RepoSkeleton(repo_name="demo", context_string="dummy context")

        cat = generate_architecture_catalog(skeleton, client=mock_client)
        self.assertEqual(cat.framework, "Flask")

        acme_dir = BASE_DIR / "demo_repo" / "acme_store"
        onboarded_cat = onboard_repository(acme_dir, client=mock_client)
        self.assertEqual(onboarded_cat.name, "acme_store")

    def test_modules_and_markdown_summary(self):
        """Verify architectural modules, subsystems, and markdown guide rendering."""
        mock_client = self._create_mock_client()
        onboarder = RepoOnboarder(client=mock_client)

        skeleton = RepoSkeleton(
            repo_name="acme_store",
            context_string="Dummy context",
        )
        catalog = onboarder.generate_catalog(skeleton)

        # Verify modules
        self.assertEqual(len(catalog.modules), 2)
        self.assertEqual(catalog.modules[0].name, "Orders & Checkout")
        self.assertEqual(catalog.modules[0].owner, "@team-orders")
        self.assertIn("routes/orders.py", catalog.modules[0].key_files)
        self.assertEqual(catalog.modules[1].name, "Payments & Refunds")
        self.assertEqual(catalog.modules[1].owner, "@team-payments")

        # Verify markdown guide output
        md = catalog.to_markdown()
        self.assertIn("# Architecture Catalog: acme_store", md)
        self.assertIn("## Architectural Modules & Subsystems", md)
        self.assertIn("### Orders & Checkout (@team-orders)", md)
        self.assertIn("### Payments & Refunds (@team-payments)", md)
        self.assertIn("## Data Models & Schemas", md)
        self.assertIn("**`Customer`** (`models.py`)", md)
        self.assertIn("## API Routes", md)
        self.assertIn("**`GET /orders`** -> `list_orders` (`routes/orders.py`)", md)
        self.assertIn("## External Integrations & Services", md)
        self.assertIn("**PaymentsGateway** (`integrations/payments_gateway.py`)", md)


if __name__ == "__main__":
    unittest.main()
