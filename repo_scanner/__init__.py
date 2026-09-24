"""Smart repository scanner package for extracting architectural skeletons."""

from pathlib import Path
from schemas import FileCategory, RepoSkeleton, ScannedFile

from .classifier import classify_file
from .formatter import build_directory_tree, generate_context_string
from .traversal import walk_repository


def scan_repo(
    repo_path: str | Path,
    max_total_chars: int = 120_000,
    max_file_chars: int = 15_000,
) -> RepoSkeleton:
    """
    Crawl a repository and extract its architectural code skeleton.

    - Filters out version control, virtualenvs, dependencies, lockfiles, and binary assets.
    - Classifies files into manifests, config, models, routes, integrations, and entrypoints.
    - Generates a compact, token-efficient architectural context string for Gemini onboarding.

    Raises:
        FileNotFoundError: If the repo_path does not exist.
        NotADirectoryError: If the repo_path is not a directory.
    """
    root = Path(repo_path).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Repository path does not exist: {repo_path}")
    if not root.is_dir():
        raise NotADirectoryError(f"Repository path is not a directory: {repo_path}")

    repo_name = root.name
    discovered_files = walk_repository(root)
    scanned_files: list[ScannedFile] = []

    for full_path, rel_path in discovered_files:
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
            size_bytes = full_path.stat().st_size
        except OSError:
            continue

        category = classify_file(rel_path, content)
        scanned_files.append(
            ScannedFile(
                path=rel_path,
                category=category,
                size_bytes=size_bytes,
                content=content,
            )
        )

    tree = build_directory_tree([f.path for f in scanned_files])
    context_string = generate_context_string(
        repo_name=repo_name,
        files=scanned_files,
        max_total_chars=max_total_chars,
        max_file_chars=max_file_chars,
    )

    return RepoSkeleton(
        repo_name=repo_name,
        root_path=str(root),
        files=scanned_files,
        tree=tree,
        context_string=context_string,
    )


__all__ = [
    "scan_repo",
    "RepoSkeleton",
    "ScannedFile",
    "FileCategory",
    "walk_repository",
    "classify_file",
    "build_directory_tree",
    "generate_context_string",
]
