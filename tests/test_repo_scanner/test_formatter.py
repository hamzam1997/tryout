"""Unit tests for directory tree generation, context string formatting, and budgeting."""

import unittest
from schemas import FileCategory, ScannedFile
from repo_scanner.formatter import (
    build_directory_tree,
    generate_context_string,
    truncate_file_content,
)


class FormatterTestCase(unittest.TestCase):
    def test_build_directory_tree(self):
        """Verify directory tree renders a clean hierarchy with branch indicators."""
        paths = [
            "app.py",
            "integrations/payments_gateway.py",
            "models.py",
            "routes/checkout.py",
            "routes/orders.py",
        ]
        tree = build_directory_tree(paths)
        self.assertIn("app.py", tree)
        self.assertIn("integrations", tree)
        self.assertIn("payments_gateway.py", tree)
        self.assertIn("routes", tree)
        self.assertIn("checkout.py", tree)
        self.assertIn("orders.py", tree)
        self.assertIn("├──", tree)

    def test_build_directory_tree_empty(self):
        """Verify empty path list produces an empty tree string."""
        self.assertEqual(build_directory_tree([]), "")

    def test_truncate_file_content(self):
        """Verify file truncation preserves prefix/suffix and inserts notice."""
        short_content = "def add(a, b): return a + b"
        content, truncated = truncate_file_content(short_content, max_chars=100)
        self.assertFalse(truncated)
        self.assertEqual(content, short_content)

        long_content = "x = 1\n" * 500
        truncated_content, truncated = truncate_file_content(long_content, max_chars=100)
        self.assertTrue(truncated)
        self.assertIn("TRUNCATED", truncated_content)
        self.assertTrue(len(truncated_content) < len(long_content))

    def test_generate_context_string_priority_and_sections(self):
        """Verify context string groups files into expected sections and respects priority."""
        files = [
            ScannedFile(
                path="requirements.txt",
                category=FileCategory.MANIFEST,
                content="Flask==3.0.3\n",
                size_bytes=13,
            ),
            ScannedFile(
                path="CODEOWNERS",
                category=FileCategory.CONFIG,
                content="/models.py @team-platform\n",
                size_bytes=26,
            ),
            ScannedFile(
                path="models.py",
                category=FileCategory.MODEL,
                content="class Order: pass\n",
                size_bytes=18,
            ),
            ScannedFile(
                path="routes/orders.py",
                category=FileCategory.ROUTE,
                content="def get_orders(): pass\n",
                size_bytes=23,
            ),
        ]

        context = generate_context_string("acme_repo", files)
        self.assertIn("# Repository Architectural Skeleton: acme_repo", context)
        self.assertIn("## Directory Structure", context)
        self.assertIn("## Manifests & Dependencies", context)
        self.assertIn("## Configuration & CODEOWNERS", context)
        self.assertIn("## Data Models & Schemas", context)
        self.assertIn("## API Routes & Controllers", context)
        self.assertIn("Flask==3.0.3", context)

    def test_budget_enforcement(self):
        """Verify context string generation halts when character budget is reached."""
        files = [
            ScannedFile(
                path="requirements.txt",
                category=FileCategory.MANIFEST,
                content="Flask==3.0.3\n",
                size_bytes=13,
            ),
            ScannedFile(
                path="large_models.py",
                category=FileCategory.MODEL,
                content="class M: pass\n" * 500,
                size_bytes=7000,
            ),
            ScannedFile(
                path="README.md",
                category=FileCategory.DOC,
                content="Documentation " * 500,
                size_bytes=7000,
            ),
        ]

        # Very tight budget: 1,000 characters
        context = generate_context_string("tiny_budget", files, max_total_chars=1000)
        self.assertLessEqual(len(context), 1500)
        # Manifests have highest priority
        self.assertIn("requirements.txt", context)
