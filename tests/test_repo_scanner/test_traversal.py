"""Unit tests for repository traversal and noise filtering."""

import tempfile
import unittest
from pathlib import Path

from repo_scanner.traversal import (
    is_binary_file,
    load_gitignore_patterns,
    matches_gitignore,
    should_ignore_dir,
    should_ignore_file,
    walk_repository,
)


class TraversalTestCase(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)

    def tearDown(self):
        self._temp_dir.cleanup()

    def test_noise_directories_and_files_filtered(self):
        """Verify .git, node_modules, venvs, lockfiles, and binary assets are ignored."""
        # Noise directories and files
        (self.root / ".git").mkdir()
        (self.root / ".git" / "HEAD").write_text("ref: refs/heads/main\n")

        (self.root / "node_modules" / "express").mkdir(parents=True)
        (self.root / "node_modules" / "express" / "index.js").write_text("module.exports = {};")

        (self.root / ".venv" / "bin").mkdir(parents=True)
        (self.root / ".venv" / "bin" / "python").write_text("#!/bin/sh")

        (self.root / "venv").mkdir()
        (self.root / "venv" / "pip.py").write_text("# pip")

        (self.root / "__pycache__").mkdir()
        (self.root / "__pycache__" / "test.cpython-312.pyc").write_bytes(b"\x00\x01\x02")

        (self.root / "dist").mkdir()
        (self.root / "dist" / "bundle.js").write_text("console.log('dist');")

        # Noise files in root
        (self.root / "package-lock.json").write_text('{"lockfileVersion": 2}')
        (self.root / "yarn.lock").write_text("# yarn lockfile v1")
        (self.root / "poetry.lock").write_text("# poetry lock")
        (self.root / "uv.lock").write_text("# uv lock")
        (self.root / ".DS_Store").write_bytes(b"\x00\x00\x00\x01")
        (self.root / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        (self.root / "archive.zip").write_bytes(b"PK\x03\x04")
        (self.root / "data.sqlite3").write_bytes(b"SQLite format 3\x00")
        (self.root / "app.min.js").write_text("var a=1;")
        (self.root / "styles.min.css").write_text("body{margin:0;}")

        # Binary file with null byte
        (self.root / "custom.blob").write_bytes(b"some\x00binary\x00data")

        # Legitimate source files
        (self.root / "app.py").write_text("print('hello')\n")
        (self.root / "models.py").write_text("class User: pass\n")
        (self.root / "requirements.txt").write_text("Flask==3.0.3\n")
        (self.root / "routes").mkdir()
        (self.root / "routes" / "orders.py").write_text("def get_orders(): pass\n")

        results = walk_repository(self.root)
        rel_paths = [rel for _, rel in results]

        expected = ["app.py", "models.py", "requirements.txt", "routes/orders.py"]
        self.assertEqual(rel_paths, sorted(expected))

    def test_gitignore_filtering(self):
        """Verify .gitignore patterns correctly exclude files and directories."""
        (self.root / ".gitignore").write_text("*.log\nsecrets/\ncustom_cache/\n")

        (self.root / "server.log").write_text("error log\n")
        (self.root / "secrets").mkdir()
        (self.root / "secrets" / "key.pem").write_text("secret-key\n")
        (self.root / "custom_cache").mkdir()
        (self.root / "custom_cache" / "cache.json").write_text("{}\n")

        (self.root / "main.py").write_text("print('main')\n")

        results = walk_repository(self.root)
        rel_paths = [rel for _, rel in results]

        self.assertIn("main.py", rel_paths)
        self.assertNotIn("server.log", rel_paths)
        self.assertNotIn("secrets/key.pem", rel_paths)
        self.assertNotIn("custom_cache/cache.json", rel_paths)

    def test_invalid_path_errors(self):
        """Verify appropriate errors are raised for invalid paths."""
        with self.assertRaises(FileNotFoundError):
            walk_repository(self.root / "non_existent_folder")

        file_path = self.root / "test.txt"
        file_path.write_text("hello")
        with self.assertRaises(NotADirectoryError):
            walk_repository(file_path)

    def test_empty_repository(self):
        """Verify an empty directory returns an empty list cleanly."""
        results = walk_repository(self.root)
        self.assertEqual(results, [])
