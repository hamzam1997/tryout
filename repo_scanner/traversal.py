"""Filesystem crawler and noise filter for repository scanning."""

import fnmatch
import os
from pathlib import Path


IGNORED_DIR_NAMES = {
    # Version control
    ".git",
    ".svn",
    ".hg",
    # Dependencies & virtual environments
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".env",
    "vendor",
    "bower_components",
    "Pods",
    ".terraform",
    # Build & distribution
    "dist",
    "build",
    "target",
    "out",
    ".next",
    ".nuxt",
    "bin",
    "obj",
    # Caches & test artifacts
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".cache",
    ".coverage",
    "htmlcov",
    # IDE & OS
    ".idea",
    ".vscode",
    ".vs",
}

IGNORED_FILE_NAMES = {
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    # Package lockfiles
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Pipfile.lock",
    "Cargo.lock",
    "go.sum",
    "composer.lock",
    "bun.lockb",
    "uv.lock",
    "pdm.lock",
}

IGNORED_EXTENSIONS = {
    # Media & Images
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".webp",
    ".bmp",
    ".tiff",
    ".mp4",
    ".mp3",
    ".wav",
    ".mov",
    ".avi",
    ".webm",
    ".flac",
    ".ogg",
    # Fonts
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".eot",
    # Archives & Compressed
    ".zip",
    ".tar",
    ".gz",
    ".tgz",
    ".bz2",
    ".xz",
    ".7z",
    ".rar",
    ".jar",
    ".war",
    # Compiled & Executables
    ".exe",
    ".bin",
    ".so",
    ".dylib",
    ".dll",
    ".obj",
    ".o",
    ".a",
    ".pyc",
    ".pyo",
    ".pyd",
    ".class",
    ".wasm",
    # Databases & serialization dumps
    ".db",
    ".sqlite",
    ".sqlite3",
    ".parquet",
    ".feather",
    ".pkl",
    ".pickle",
    ".h5",
    ".onnx",
    ".pt",
    ".pth",
    # Source maps
    ".map",
}


def load_gitignore_patterns(repo_root: Path) -> list[str]:
    """Parse .gitignore from repo root into clean matching patterns."""
    gitignore_file = repo_root / ".gitignore"
    if not gitignore_file.is_file():
        return []

    patterns: list[str] = []
    try:
        with open(gitignore_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
    except OSError:
        pass
    return patterns


def matches_gitignore(rel_path: str, is_dir: bool, patterns: list[str]) -> bool:
    """Check if a relative path matches any parsed .gitignore pattern."""
    # Normalize path separators to forward slash
    norm_path = rel_path.replace(os.sep, "/")
    base_name = os.path.basename(norm_path)

    for pat in patterns:
        pat = pat.replace(os.sep, "/")
        # Directory-only pattern (e.g. "build/")
        if pat.endswith("/"):
            if not is_dir:
                continue
            clean_pat = pat.rstrip("/")
            if fnmatch.fnmatch(norm_path, clean_pat) or fnmatch.fnmatch(
                norm_path, f"*/{clean_pat}"
            ) or fnmatch.fnmatch(base_name, clean_pat):
                return True
        else:
            if fnmatch.fnmatch(norm_path, pat) or fnmatch.fnmatch(
                norm_path, f"*/{pat}"
            ) or fnmatch.fnmatch(base_name, pat):
                return True
    return False


def is_binary_file(file_path: Path) -> bool:
    """Detect if a file contains binary content via null-byte inspection."""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            return b"\0" in chunk
    except OSError:
        return True


def should_ignore_dir(dir_name: str, rel_path: str, gitignore_patterns: list[str]) -> bool:
    """Determine whether to prune a directory during traversal."""
    if dir_name in IGNORED_DIR_NAMES:
        return True
    if matches_gitignore(rel_path, is_dir=True, patterns=gitignore_patterns):
        return True
    return False


def should_ignore_file(
    file_name: str,
    rel_path: str,
    full_path: Path,
    gitignore_patterns: list[str],
) -> bool:
    """Determine whether to filter out a file."""
    if file_name in IGNORED_FILE_NAMES:
        return True

    # Check minified web assets
    lower_name = file_name.lower()
    if lower_name.endswith(".min.js") or lower_name.endswith(".min.css"):
        return True

    # Check extension
    _, ext = os.path.splitext(lower_name)
    if ext in IGNORED_EXTENSIONS:
        return True

    # Check gitignore
    if matches_gitignore(rel_path, is_dir=False, patterns=gitignore_patterns):
        return True

    # Check binary content
    if is_binary_file(full_path):
        return True

    return False


def walk_repository(repo_path: str | Path) -> list[tuple[Path, str]]:
    """
    Traverse repository files, filtering out noise and non-code assets.

    Returns a sorted list of (absolute_path, relative_posix_path) tuples.
    Raises FileNotFoundError if repo_path does not exist.
    """
    root = Path(repo_path).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Repository path does not exist: {repo_path}")
    if not root.is_dir():
        raise NotADirectoryError(f"Repository path is not a directory: {repo_path}")

    gitignore_patterns = load_gitignore_patterns(root)
    collected: list[tuple[Path, str]] = []

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir == ".":
            rel_dir = ""

        # In-place directory pruning to avoid traversing ignored subtrees
        dirnames[:] = [
            d
            for d in dirnames
            if not should_ignore_dir(
                d,
                f"{rel_dir}/{d}" if rel_dir else d,
                gitignore_patterns,
            )
        ]

        for filename in filenames:
            rel_file = f"{rel_dir}/{filename}" if rel_dir else filename
            rel_file_posix = rel_file.replace(os.sep, "/")
            full_file = Path(dirpath) / filename

            if should_ignore_file(filename, rel_file_posix, full_file, gitignore_patterns):
                continue

            collected.append((full_file, rel_file_posix))

    # Deterministic sorting
    collected.sort(key=lambda item: item[1])
    return collected
