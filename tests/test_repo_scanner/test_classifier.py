"""Unit tests for semantic file classification."""

import unittest
from schemas import FileCategory
from repo_scanner.classifier import classify_file


class ClassifierTestCase(unittest.TestCase):
    def test_manifest_classification(self):
        """Verify package managers and dependency manifests are categorized as MANIFEST."""
        manifest_paths = [
            "requirements.txt",
            "pyproject.toml",
            "setup.py",
            "Pipfile",
            "package.json",
            "go.mod",
            "Cargo.toml",
            "Gemfile",
            "pom.xml",
            "build.gradle",
            "composer.json",
        ]
        for path in manifest_paths:
            with self.subTest(path=path):
                self.assertEqual(classify_file(path), FileCategory.MANIFEST)

    def test_config_and_codeowners_classification(self):
        """Verify configuration, container definitions, and CODEOWNERS are categorized as CONFIG."""
        config_paths = [
            "CODEOWNERS",
            ".github/CODEOWNERS",
            ".env.example",
            ".env.sample",
            "docker-compose.yml",
            "Dockerfile",
            "Makefile",
            "tsconfig.json",
        ]
        for path in config_paths:
            with self.subTest(path=path):
                self.assertEqual(classify_file(path), FileCategory.CONFIG)

    def test_entrypoint_classification(self):
        """Verify application entrypoints at root or src are categorized as ENTRYPOINT."""
        entrypoints = [
            "app.py",
            "main.py",
            "server.py",
            "wsgi.py",
            "index.ts",
            "server.ts",
            "main.go",
            "src/app.py",
            "src/index.js",
        ]
        for path in entrypoints:
            with self.subTest(path=path):
                self.assertEqual(classify_file(path), FileCategory.ENTRYPOINT)

    def test_model_classification(self):
        """Verify models, schemas, and database entities are categorized as MODEL."""
        model_paths = [
            "models.py",
            "schemas.py",
            "models/user.py",
            "app/models/order.py",
            "schemas/payment.py",
            "entities/account.py",
            "types/user.ts",
            "schema.prisma",
            "schema.sql",
            "models.go",
            "user.model.ts",
        ]
        for path in model_paths:
            with self.subTest(path=path):
                self.assertEqual(classify_file(path), FileCategory.MODEL)

        # Content-based classification for model
        code_with_model = "class Account(BaseModel):\n    id: int\n"
        self.assertEqual(classify_file("account.py", content=code_with_model), FileCategory.MODEL)

    def test_route_classification(self):
        """Verify API routes, controllers, endpoints, and views are categorized as ROUTE."""
        route_paths = [
            "routes/orders.py",
            "routes/checkout.py",
            "controllers/user.ts",
            "api/v1/refunds.py",
            "endpoints/auth.py",
            "handlers/webhook.go",
            "views/dashboard.py",
            "routes.py",
            "user.controller.ts",
        ]
        for path in route_paths:
            with self.subTest(path=path):
                self.assertEqual(classify_file(path), FileCategory.ROUTE)

        # Content-based classification for routes
        code_with_route = "@app.route('/test')\ndef test_fn(): pass\n"
        self.assertEqual(classify_file("custom_endpoints.py", content=code_with_route), FileCategory.ROUTE)

    def test_integration_classification(self):
        """Verify external adapters, gateways, and client integrations are categorized as INTEGRATION."""
        integration_paths = [
            "integrations/payments_gateway.py",
            "integrations/stripe.py",
            "services/notification_service.py",
            "clients/slack_client.py",
            "adapters/email_adapter.py",
        ]
        for path in integration_paths:
            with self.subTest(path=path):
                self.assertEqual(classify_file(path), FileCategory.INTEGRATION)

    def test_documentation_and_other_classification(self):
        """Verify documentation and general supporting files are categorized as DOC and OTHER."""
        self.assertEqual(classify_file("README.md"), FileCategory.DOC)
        self.assertEqual(classify_file("ARCHITECTURE.md"), FileCategory.DOC)
        self.assertEqual(classify_file("store.py"), FileCategory.OTHER)
        self.assertEqual(classify_file("utils/string_helpers.py"), FileCategory.OTHER)

    def test_test_files_classification(self):
        """Verify test files are classified as OTHER and never misclassified as MODEL or ROUTE."""
        test_paths = [
            "tests/test_orders.py",
            "tests/routes/test_routes.py",
            "tests/models/test_user.py",
            "test_checkout.py",
            "order.test.ts",
            "src/__tests__/app.spec.js",
        ]
        for path in test_paths:
            with self.subTest(path=path):
                self.assertEqual(classify_file(path), FileCategory.OTHER)
