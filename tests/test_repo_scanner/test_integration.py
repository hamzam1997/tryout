"""Integration test scanning demo_repo/acme_store."""

import unittest
from pathlib import Path
from config import BASE_DIR
from repo_scanner import scan_repo
from schemas import FileCategory


class DemoRepoScannerIntegrationTestCase(unittest.TestCase):
    def test_scan_acme_store(self):
        """Verify scan_repo extracts complete architectural skeleton from demo_repo/acme_store."""
        acme_dir = BASE_DIR / "demo_repo" / "acme_store"
        self.assertTrue(acme_dir.exists(), f"Demo repo not found at {acme_dir}")

        skeleton = scan_repo(acme_dir)

        # Basic metadata
        self.assertEqual(skeleton.repo_name, "acme_store")
        self.assertTrue(len(skeleton.files) > 0)
        self.assertTrue(len(skeleton.tree) > 0)
        self.assertTrue(len(skeleton.context_string) > 0)

        # File classification checks
        manifest_paths = [f.path for f in skeleton.manifests]
        self.assertIn("requirements.txt", manifest_paths)

        config_paths = [f.path for f in skeleton.configs]
        self.assertIn("CODEOWNERS", config_paths)
        self.assertIn(".env.example", config_paths)

        model_paths = [f.path for f in skeleton.models]
        self.assertIn("models.py", model_paths)

        route_paths = [f.path for f in skeleton.routes]
        self.assertIn("routes/orders.py", route_paths)
        self.assertIn("routes/checkout.py", route_paths)
        self.assertIn("routes/refunds.py", route_paths)

        integration_paths = [f.path for f in skeleton.integrations]
        self.assertIn("integrations/payments_gateway.py", integration_paths)

        entrypoint_paths = [f.path for f in skeleton.entrypoints]
        self.assertIn("app.py", entrypoint_paths)

        doc_paths = [f.path for f in skeleton.docs]
        self.assertIn("README.md", doc_paths)

        # Context string content validation
        context = skeleton.context_string
        self.assertIn("# Repository Architectural Skeleton: acme_store", context)
        self.assertIn("## Directory Structure", context)
        self.assertIn("## Manifests & Dependencies", context)
        self.assertIn("## Configuration & CODEOWNERS", context)
        self.assertIn("## Data Models & Schemas", context)
        self.assertIn("## API Routes & Controllers", context)
        self.assertIn("## External Integrations & Clients", context)
        self.assertIn("@team-payments", context)
        self.assertIn("Payment", context)
        self.assertIn("/refunds", context)
