"""Semantic classification of repository files for architectural context extraction."""

import os
from pathlib import Path
from schemas import FileCategory

MANIFEST_FILENAMES = {
    # Python
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "Pipfile",
    # JavaScript / TypeScript
    "package.json",
    # Go
    "go.mod",
    # Rust
    "Cargo.toml",
    # Ruby
    "Gemfile",
    # Java / Kotlin
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    # PHP
    "composer.json",
    # Elixir
    "mix.exs",
}

CONFIG_FILENAMES = {
    "CODEOWNERS",
    ".env.example",
    ".env.sample",
    ".env.template",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Dockerfile",
    "Procfile",
    "Makefile",
    "tsconfig.json",
}

ENTRYPOINT_FILENAMES = {
    "app.py",
    "main.py",
    "server.py",
    "wsgi.py",
    "asgi.py",
    "run.py",
    "index.ts",
    "server.ts",
    "main.ts",
    "index.js",
    "server.js",
    "main.js",
    "main.go",
}

DOC_FILENAMES = {
    "README.md",
    "ARCHITECTURE.md",
    "API.md",
    "DESIGN.md",
    "CONTRIBUTING.md",
}

MODEL_DIR_KEYWORDS = {"models", "schemas", "entities", "types"}
ROUTE_DIR_KEYWORDS = {"routes", "controllers", "endpoints", "api", "handlers", "views"}
INTEGRATION_DIR_KEYWORDS = {"integrations", "services", "clients", "adapters"}


def classify_file(rel_path: str, content: str = "") -> FileCategory:
    """
    Classify a repository file into its primary architectural category.

    rel_path: POSIX relative path from the repository root.
    content: Optional file content string to aid classification.
    """
    norm_path = rel_path.replace(os.sep, "/")
    base_name = os.path.basename(norm_path)
    lower_base = base_name.lower()
    path_parts = [p.lower() for p in norm_path.split("/")[:-1]]

    # 1. Project Manifests
    if base_name in MANIFEST_FILENAMES:
        return FileCategory.MANIFEST

    # 2. Project Configuration & CODEOWNERS
    if base_name in CONFIG_FILENAMES or norm_path.endswith("/CODEOWNERS"):
        return FileCategory.CONFIG

    # 3. Documentation
    if base_name in DOC_FILENAMES:
        return FileCategory.DOC

    # 4. Entrypoint (top-level or immediate src/ entrypoint)
    if (len(path_parts) <= 1 or path_parts == ["src"]) and lower_base in ENTRYPOINT_FILENAMES:
        return FileCategory.ENTRYPOINT

    # Exclude test files/directories from being classified as architectural models/routes
    if (
        any(k in path_parts for k in {"tests", "test", "__tests__", "spec", "specs"})
        or lower_base.startswith("test_")
        or lower_base.endswith(("_test.py", ".test.ts", ".spec.ts", ".test.js", ".spec.js"))
    ):
        return FileCategory.OTHER

    # 5. Data Models & Schemas
    if any(k in path_parts for k in MODEL_DIR_KEYWORDS):
        return FileCategory.MODEL

    if lower_base in {
        "models.py",
        "model.py",
        "schemas.py",
        "schema.py",
        "entities.py",
        "types.py",
        "models.go",
        "schema.go",
        "types.go",
        "schema.prisma",
        "schema.sql",
    }:
        return FileCategory.MODEL

    if lower_base.endswith((".model.ts", ".model.js", ".schema.ts", ".schema.js")):
        return FileCategory.MODEL

    # 6. API Routes & Controllers
    if any(k in path_parts for k in ROUTE_DIR_KEYWORDS):
        return FileCategory.ROUTE

    if lower_base in {
        "routes.py",
        "route.py",
        "controllers.py",
        "controller.py",
        "endpoints.py",
        "handlers.py",
        "views.py",
        "api.py",
    }:
        return FileCategory.ROUTE

    if any(
        lower_base.endswith(suffix)
        for suffix in (
            "routes.py",
            "route.py",
            "controller.py",
            "controllers.py",
            "handler.py",
            "handlers.py",
            "endpoint.py",
            "endpoints.py",
            "view.py",
            "views.py",
            ".controller.ts",
            ".route.ts",
        )
    ):
        return FileCategory.ROUTE

    # 7. External Integrations & Service Adapters
    if any(k in path_parts for k in INTEGRATION_DIR_KEYWORDS):
        return FileCategory.INTEGRATION

    if any(
        lower_base.endswith(suffix)
        for suffix in (
            "gateway.py",
            "client.py",
            "adapter.py",
            "_service.py",
            "service.py",
            ".client.ts",
            ".service.ts",
        )
    ):
        return FileCategory.INTEGRATION

    # 8. Content-based cues if content is available
    if content:
        # Route markers
        if any(marker in content for marker in ("@app.route", "@bp.route", "@router.", "router.get", "app.get(")):
            return FileCategory.ROUTE

        # Model markers
        if any(marker in content for marker in ("BaseModel", "db.Model", "declarative_base", "models.Model")):
            return FileCategory.MODEL

    return FileCategory.OTHER
