"""Git and GitHub repository management utilities.

Supports cloning or streaming GitHub repositories into local caches for scanning,
handling OAuth tokens securely in-memory without persisting credentials to disk.
"""

from __future__ import annotations

import base64
import io
import logging
import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path

import requests

from config import settings

logger = logging.getLogger(__name__)

GITHUB_REPO_REGEX = re.compile(
    r"^(?:https?://github\.com/|git@github\.com:)?([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+?)(?:\.git)?$"
)


def parse_github_slug(url_or_slug: str) -> tuple[str, str]:
    """Extract (owner, repo) from a GitHub URL or 'owner/repo' shorthand."""
    cleaned = url_or_slug.strip().rstrip("/")
    match = GITHUB_REPO_REGEX.match(cleaned)
    if not match:
        raise ValueError(
            f"Invalid GitHub repository identifier: '{url_or_slug}'. Expected format 'owner/repo' or 'https://github.com/owner/repo'."
        )
    return match.group(1), match.group(2)


def fetch_github_repository(
    url_or_slug: str,
    branch: str | None = None,
    access_token: str | None = None,
    dest_dir: Path | None = None,
    force_refresh: bool = False,
) -> tuple[Path, str, str]:
    """Fetch a GitHub repository into a local directory.

    Attempts a shallow git clone first (passing authorization in memory headers),
    falling back to GitHub's tarball archive API if git is unavailable.

    Returns:
        (repo_path, commit_sha, repo_full_name)
    """
    owner, repo = parse_github_slug(url_or_slug)
    full_name = f"{owner}/{repo}"

    base_cache = dest_dir or settings.repos_cache_dir
    base_cache.mkdir(parents=True, exist_ok=True)
    target_path = base_cache / f"{owner}_{repo}"

    if target_path.exists():
        if force_refresh:
            shutil.rmtree(target_path, ignore_errors=True)
        else:
            # Check if existing target has a valid git commit or directory
            commit_sha = _resolve_existing_commit(target_path)
            if commit_sha:
                logger.info("Reusing existing local cache for %s (%s)", full_name, commit_sha[:8])
                return target_path, commit_sha, full_name
            shutil.rmtree(target_path, ignore_errors=True)

    target_path.mkdir(parents=True, exist_ok=True)

    # 1. Try shallow git clone with in-memory auth header
    try:
        commit_sha = _git_shallow_clone(owner, repo, branch, access_token, target_path)
        logger.info("Successfully shallow cloned %s (%s)", full_name, commit_sha[:8])
        return target_path, commit_sha, full_name
    except Exception as git_err:
        logger.warning(
            "git clone failed or git is unavailable (%s). Falling back to GitHub tarball API.",
            git_err,
        )

    # 2. Fallback to GitHub tarball archive API
    commit_sha = _download_and_extract_tarball(owner, repo, branch, access_token, target_path)
    logger.info("Successfully extracted tarball archive for %s (%s)", full_name, commit_sha[:8])
    return target_path, commit_sha, full_name


def _git_shallow_clone(
    owner: str,
    repo: str,
    branch: str | None,
    token: str | None,
    target_dir: Path,
) -> str:
    """Perform a shallow clone without persisting secrets to the git remote."""
    clone_url = f"https://github.com/{owner}/{repo}.git"
    cmd = ["git"]

    if token:
        # Pass authorization header in memory only for this invocation.
        # Git-over-HTTPS rejects Bearer; GitHub expects basic x-access-token.
        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        cmd.extend(["-c", f"http.extraHeader=Authorization: basic {basic}"])

    cmd.extend(["clone", "--depth", "1"])
    if branch:
        cmd.extend(["-b", branch])

    cmd.extend([clone_url, str(target_dir)])

    # Run git clone
    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=settings.execution_timeout_seconds,
    )
    if res.returncode != 0:
        # Clean any partial clone
        shutil.rmtree(target_dir, ignore_errors=True)
        target_dir.mkdir(parents=True, exist_ok=True)
        raise RuntimeError(f"git clone failed: {res.stderr.strip() or res.stdout.strip()}")

    # Extract commit SHA
    rev_res = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=target_dir,
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    return rev_res.stdout.strip()


def _download_and_extract_tarball(
    owner: str,
    repo: str,
    branch: str | None,
    token: str | None,
    target_dir: Path,
) -> str:
    """Download tarball from GitHub API and unpack directly into target_dir."""
    ref = branch or "HEAD"
    api_url = f"https://api.github.com/repos/{owner}/{repo}/tarball/{ref}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "tryout-app",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    resp = requests.get(api_url, headers=headers, stream=True, timeout=30)
    if resp.status_code == 404:
        raise ValueError(f"Repository '{owner}/{repo}' or branch '{ref}' not found on GitHub.")
    if resp.status_code == 401 or resp.status_code == 403:
        raise PermissionError(
            f"Access denied to '{owner}/{repo}'. Ensure GitHub OAuth token has 'repo' scope."
        )
    resp.raise_for_status()

    # The tarball has a root directory like `owner-repo-sha/`. We extract its contents.
    tar_bytes = io.BytesIO(resp.content)
    with tarfile.open(fileobj=tar_bytes, mode="r:gz") as tar:
        # Find common root prefix
        members = tar.getmembers()
        if not members:
            raise RuntimeError("Downloaded empty repository tarball.")

        root_prefix = members[0].name.split("/")[0]
        commit_sha = ""
        # GitHub names the root directory `{owner}-{repo}-{short_sha}`
        if "-" in root_prefix:
            commit_sha = root_prefix.rsplit("-", 1)[-1]

        for member in members:
            # Strip the root prefix so contents extract directly into target_dir
            if "/" in member.name:
                member.name = member.name.split("/", 1)[1]
                if member.name:
                    # "data" refuses absolute paths, ".." escapes, links out and device files.
                    tar.extract(member, path=target_dir, filter="data")

    return commit_sha or "tarball-head"


def _resolve_existing_commit(target_dir: Path) -> str | None:
    """Check if target_dir has an existing commit SHA."""
    git_dir = target_dir / ".git"
    if git_dir.exists():
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=target_dir,
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            sha = res.stdout.strip()
            if sha:
                return sha
        except Exception:
            pass
    return None
