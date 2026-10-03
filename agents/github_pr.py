"""Publish a generated attempt as a GitHub pull request."""

from __future__ import annotations

import base64
import os
import subprocess
from pathlib import Path
from urllib.parse import quote

import requests

from agents.git_utils import parse_github_slug


GITHUB_API = "https://api.github.com"


def _git(root: Path, *args: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    if result.returncode:
        message = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise RuntimeError(message)
    return result.stdout.strip()


def _github_request(method: str, url: str, token: str, **kwargs):
    response = requests.request(
        method,
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30,
        **kwargs,
    )
    if not response.ok:
        try:
            detail = response.json().get("message") or response.text
        except ValueError:
            detail = response.text
        raise RuntimeError(f"GitHub API returned {response.status_code}: {detail[:500]}")
    return response.json()


def create_attempt_pull_request(
    *,
    root: Path,
    repository_source: str,
    token: str | None,
    attempt_id: int,
    idea_id: int,
    idea_title: str,
    summary: str,
    repo_ref: str,
    change_paths: list[str],
) -> tuple[str, str, str] | None:
    """Commit generated files and open a PR against the repository's ``main`` branch.

    Returns ``(branch, base_branch, PR URL)``. Non-GitHub sources keep the
    generated patch in the app but cannot publish a hosted pull request.
    """
    try:
        owner, name = parse_github_slug(repository_source)
    except ValueError:
        try:
            remote = _git(root, "remote", "get-url", "origin")
            owner, name = parse_github_slug(remote)
        except (RuntimeError, ValueError):
            return None
    if not token:
        raise RuntimeError("Connect GitHub with repository write access to open a pull request.")
    if not change_paths:
        return None

    root = root.resolve()
    if not (root / ".git").exists():
        raise RuntimeError("The repository checkout has no Git history; cannot create a pull request.")

    base_branch = "main"
    branch_data = _github_request(
        "GET",
        f"{GITHUB_API}/repos/{owner}/{name}/branches/{quote(base_branch, safe='')}",
        token,
    )
    base_sha = branch_data["commit"]["sha"]
    if base_sha != repo_ref:
        raise RuntimeError(
            "The repository's main branch changed after idea extraction. "
            "Refresh its catalog and retry so the pull request is based on current code."
        )

    current_sha = _git(root, "rev-parse", "HEAD")
    if current_sha != repo_ref:
        raise RuntimeError("The isolated checkout does not match the idea's repository snapshot.")

    branch = f"tryout/idea-{idea_id}-attempt-{attempt_id}"
    _git(root, "checkout", "-b", branch)
    for path in change_paths:
        _git(root, "add", "--", f":(literal){path}")
    if not _git(root, "diff", "--cached", "--name-only"):
        return None

    _git(
        root,
        "-c", "core.hooksPath=/dev/null",
        "-c", "user.name=Tryout Coding Agent",
        "-c", "user.email=tryout-coding-agent@users.noreply.github.com",
        "commit", "-m", f"feat: {idea_title[:60]}",
    )

    encoded_auth = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    push_env = os.environ.copy()
    push_env.update({
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
        "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {encoded_auth}",
    })
    _git(
        root, "-c", "core.hooksPath=/dev/null", "push", "--set-upstream", "origin", branch,
        env=push_env,
    )

    body = (
        f"## Summary\n{summary[:4000]}\n\n"
        f"Generated from approved idea #{idea_id} by Tryout.\n\n"
        "A prototype test suite is included, with mocks for required external services. "
        "Generated code was not executed by the attempt worker."
    )
    pr = _github_request(
        "POST",
        f"{GITHUB_API}/repos/{owner}/{name}/pulls",
        token,
        json={
            "title": " ".join(idea_title.split())[:256] or f"Tryout attempt #{attempt_id}",
            "head": branch,
            "base": base_branch,
            "body": body,
        },
    )
    return branch, base_branch, pr["html_url"]
