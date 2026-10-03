"""GitHub OAuth authentication and repository listing endpoints."""

from __future__ import annotations

import logging
import secrets
from urllib.parse import urlencode

import requests
from flask import Blueprint, jsonify, redirect, request, session

from config import settings

logger = logging.getLogger(__name__)

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _get_redirect_uri() -> str:
    """Determine the OAuth callback redirect URI."""
    if settings.github_redirect_uri:
        return settings.github_redirect_uri
    # Derive from the incoming request (supports local dev and cloud run https)
    host_url = request.host_url.rstrip("/")
    # Force https if forwarded proto is https
    if request.headers.get("X-Forwarded-Proto") == "https" and host_url.startswith("http://"):
        host_url = "https://" + host_url[len("http://") :]
    return f"{host_url}/api/auth/github/callback"


@bp.get("/github/login")
def github_login():
    """Initiate GitHub OAuth web flow."""
    client_id = settings.github_client_id.strip("'\" \t\r\n")
    client_secret = settings.github_client_secret.strip("'\" \t\r\n")
    if not client_id or not client_secret:
        return (
            jsonify(
                {
                    "error": "GitHub OAuth is not configured on this server.",
                    "detail": "Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET in the environment.",
                }
            ),
            503,
        )

    state = secrets.token_urlsafe(16)
    redirect_uri = _get_redirect_uri()
    session["oauth_state"] = state
    session["oauth_redirect_uri"] = redirect_uri

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "repo,read:user",
        "state": state,
    }
    github_url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"
    return redirect(github_url)


@bp.get("/github/callback")
def github_callback():
    """Handle callback from GitHub OAuth."""
    error = request.args.get("error")
    if error:
        error_desc = request.args.get("error_description", error)
        logger.warning("GitHub OAuth error returned: %s", error_desc)
        return redirect(f"/?auth_error={error_desc}")

    state = request.args.get("state")
    expected_state = session.get("oauth_state")
    if not state or state != expected_state:
        logger.warning("OAuth state mismatch: received '%s' vs expected '%s'", state, expected_state)
        return redirect("/?auth_error=State+mismatch.+Please+try+connecting+again.")

    code = request.args.get("code")
    if not code:
        return redirect("/?auth_error=No+code+received+from+GitHub.")

    redirect_uri = session.get("oauth_redirect_uri") or _get_redirect_uri()
    client_id = settings.github_client_id.strip("'\" \t\r\n")
    client_secret = settings.github_client_secret.strip("'\" \t\r\n")

    # Exchange code for access token
    token_url = "https://github.com/login/oauth/access_token"
    token_payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }
    headers = {"Accept": "application/json", "User-Agent": "tryout-app"}

    try:
        resp = requests.post(token_url, json=token_payload, headers=headers, timeout=15)
        resp.raise_for_status()
        token_data = resp.json()
    except Exception as exc:
        logger.exception("Failed to exchange GitHub authorization code: %s", exc)
        return redirect("/?auth_error=Failed+to+exchange+GitHub+authorization+code.")

    access_token = token_data.get("access_token")
    if not access_token:
        err_msg = token_data.get("error_description", "Failed to retrieve access token from GitHub")
        return redirect(f"/?auth_error={err_msg}")

    # Fetch user details
    user_data = None
    try:
        user_resp = requests.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}", "User-Agent": "tryout-app"},
            timeout=10,
        )
        if user_resp.status_code == 200:
            user_json = user_resp.json()
            user_data = {
                "login": user_json.get("login"),
                "avatar_url": user_json.get("avatar_url"),
                "name": user_json.get("name") or user_json.get("login"),
            }
    except Exception as user_err:
        logger.warning("Could not fetch user profile from GitHub: %s", user_err)

    session["github_token"] = access_token
    if user_data:
        session["github_user"] = user_data

    session.pop("oauth_state", None)
    session.pop("oauth_redirect_uri", None)

    return redirect("/?auth_success=1")


@bp.get("/firebase-config")
def firebase_config():
    """Return public Firebase client configuration from server settings or Secret Manager."""
    project_id = settings.firebase_project_id or settings.google_cloud_project
    return jsonify(
        {
            "apiKey": settings.firebase_api_key,
            "authDomain": settings.firebase_auth_domain or (f"{project_id}.firebaseapp.com" if project_id else ""),
            "projectId": project_id,
            "storageBucket": settings.firebase_storage_bucket or (f"{project_id}.firebasestorage.app" if project_id else ""),
            "messagingSenderId": settings.firebase_messaging_sender_id,
            "appId": settings.firebase_app_id,
        }
    )


@bp.post("/firebase-sync")
def firebase_sync():
    """Sync Firebase authenticated user and optional GitHub access token."""
    body = request.get_json(silent=True) or {}
    github_token = body.get("github_token")
    firebase_user = body.get("user") or {}

    if github_token:
        session["github_token"] = github_token
        try:
            user_resp = requests.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {github_token}", "User-Agent": "tryout-app"},
                timeout=10,
            )
            if user_resp.status_code == 200:
                user_json = user_resp.json()
                session["github_user"] = {
                    "login": user_json.get("login"),
                    "avatar_url": user_json.get("avatar_url"),
                    "name": user_json.get("name") or user_json.get("login"),
                }
        except Exception as exc:
            logger.warning("Could not fetch user profile from GitHub in firebase-sync: %s", exc)

    if firebase_user:
        session["user"] = firebase_user

    user_info = session.get("github_user") or session.get("user")
    return jsonify(
        {
            "ok": True,
            "authenticated": bool(session.get("github_token")),
            "user": user_info,
        }
    )


@bp.get("/github/status")
def github_status():
    """Return the current GitHub authentication state."""
    has_creds = bool(settings.github_client_id and settings.github_client_secret)
    token = session.get("github_token")
    user = session.get("github_user") or session.get("user")

    return jsonify(
        {
            "configured": has_creds or bool(token),
            "authenticated": bool(token),
            "user": user if token else None,
        }
    )


@bp.post("/github/logout")
def github_logout():
    """Clear the GitHub session."""
    session.pop("github_token", None)
    session.pop("github_user", None)
    return jsonify({"ok": True, "authenticated": False})


@bp.get("/github/repos")
def github_repos():
    """Fetch repositories accessible to the authenticated user."""
    token = session.get("github_token")
    if not token:
        return jsonify({"error": "Unauthorized. Please connect with GitHub first."}), 401

    api_url = "https://api.github.com/user/repos"
    params = {
        "sort": "updated",
        "per_page": 100,
        "affiliation": "owner,collaborator,organization_member",
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "tryout-app",
    }

    try:
        resp = requests.get(api_url, params=params, headers=headers, timeout=15)
        if resp.status_code == 401:
            session.pop("github_token", None)
            session.pop("github_user", None)
            return jsonify({"error": "GitHub session expired. Please reconnect."}), 401
        resp.raise_for_status()
        raw_repos = resp.json()
    except Exception as exc:
        logger.exception("Failed to query GitHub repositories: %s", exc)
        return jsonify({"error": f"Failed to query GitHub repositories: {exc}"}), 502

    repos = []
    for r in raw_repos:
        repos.append(
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "full_name": r.get("full_name"),
                "private": r.get("private", False),
                "description": r.get("description") or "",
                "default_branch": r.get("default_branch") or "main",
                "html_url": r.get("html_url"),
                "updated_at": r.get("updated_at"),
            }
        )

    return jsonify(repos)
