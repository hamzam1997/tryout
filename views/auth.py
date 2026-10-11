"""GitHub OAuth authentication and repository listing endpoints."""

from __future__ import annotations

import logging
import secrets
from urllib.parse import urlencode

import firebase_admin
import requests
from firebase_admin import auth as firebase_auth
from flask import Blueprint, g, jsonify, redirect, request, session

import database as db
from config import settings
from schemas import WorkspaceRole
from seed_history import seed_friction_history

logger = logging.getLogger(__name__)

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# API paths a signed-out browser must reach to sign in.
_PUBLIC_API = {
    "/api/auth/firebase-config",
    "/api/auth/firebase-sync",
    "/api/auth/me",
    "/api/auth/logout",
    "/api/auth/github/login",
    "/api/auth/github/callback",
    "/api/auth/github/status",
}


def require_login():
    """`before_request` hook: every /api call needs a server-verified user and runs in
    one of that user's workspaces. All database reads and writes are scoped to it."""
    db.set_workspace(None)  # worker threads are reused; never inherit the last request's
    if not request.path.startswith("/api/") or request.path in _PUBLIC_API:
        return None
    user = session.get("user") or {}
    if not user.get("uid"):
        return jsonify({"error": "Sign in required."}), 401

    membership = _resolve_membership(user)
    if membership is None:
        return jsonify({"error": "You are not a member of that workspace."}), 403
    db.set_workspace(membership.workspace_id)
    g.membership = membership
    if not _role_allows(membership.role):
        return jsonify({"error": "Only a workspace admin or owner can do that."}), 403
    return None


# Members read, approve, reject and run attempts. Changing what the workspace works
# on (repositories, meetings) and deleting ideas needs an admin or owner.
# Workspace, member and invitation endpoints check roles per workspace themselves.
_ADMIN_WRITE_PREFIXES = ("/api/repositories", "/api/meetings")


def _role_allows(role: WorkspaceRole) -> bool:
    if role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN) or request.method in ("GET", "HEAD", "OPTIONS"):
        return True
    if request.path.startswith(_ADMIN_WRITE_PREFIXES):
        return False
    return not (request.method == "DELETE" and request.path.startswith("/api/ideas/"))


def _resolve_membership(user: dict):
    """The workspace asked for (header, else last used), or the user's first one."""
    uid = user["uid"]
    wanted = request.headers.get("X-Workspace-Id") or session.get("workspace_id")
    if wanted:
        membership = db.get_membership(int(wanted), uid)
        if membership or request.headers.get("X-Workspace-Id"):
            if membership:
                session["workspace_id"] = membership.workspace_id
            return membership  # an explicit header for a foreign workspace is a 403
    memberships = db.list_memberships(uid=uid)
    membership = memberships[0] if memberships else _create_personal_workspace(user)
    session["workspace_id"] = membership.workspace_id
    return membership


def _create_personal_workspace(user: dict):
    name = f"{user.get('name') or user.get('email') or 'My'}'s workspace"
    workspace = db.create_workspace(name, user["uid"])
    if settings.seed_demo_data:
        db.set_workspace(workspace.id)
        seed_friction_history()
    return db.get_membership(workspace.id, user["uid"])


def _verify_id_token(id_token: str) -> dict:
    """Decoded claims of a Firebase ID token; raises if it is invalid or expired."""
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(options={"projectId": settings.firebase_project_id})
    return firebase_auth.verify_id_token(id_token)


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
        # Generate stable UID for GitHub user and persist to Firestore
        gh_uid = f"github:{user_data.get('login')}"
        session["user"] = {
            "uid": gh_uid,
            "email": user_json.get("email") if "user_json" in locals() and user_json.get("email") else f"{user_data.get('login')}@users.noreply.github.com",
            "name": user_data.get("name"),
            "avatar_url": user_data.get("avatar_url"),
        }
        try:
            db.upsert_user(
                uid=gh_uid,
                email=session["user"]["email"],
                name=user_data.get("name"),
                avatar_url=user_data.get("avatar_url"),
                provider="github",
                github_login=user_data.get("login"),
            )
        except Exception as db_err:
            logger.warning("Could not persist GitHub user to Firestore: %s", db_err)

    session.pop("oauth_state", None)
    session.pop("oauth_redirect_uri", None)

    return redirect("/?auth_success=1")


@bp.get("/firebase-config")
def firebase_config():
    """Return public Firebase client configuration from server environment/secrets."""
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
    # Identity comes only from the verified ID token, never from client-sent fields.
    try:
        claims = _verify_id_token(body.get("id_token") or "")
    except Exception as exc:
        logger.info("Rejected firebase-sync with an invalid ID token: %s", exc)
        return jsonify({"error": "Invalid or expired sign-in token."}), 401
    firebase_user = {
        "uid": claims["uid"],
        "email": claims.get("email"),
        "name": claims.get("name") or claims.get("email"),
        "avatar_url": claims.get("picture"),
        "email_verified": bool(claims.get("email_verified")),
    }

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
        session.permanent = True  # survives browser restarts (PERMANENT_SESSION_LIFETIME)

    # Upsert user record into Firestore /users collection
    uid = firebase_user.get("uid")
    saved_user = None
    if uid:
        try:
            gh_user = session.get("github_user") or {}
            saved_user = db.upsert_user(
                uid=uid,
                email=firebase_user.get("email"),
                name=firebase_user.get("name") or gh_user.get("name"),
                avatar_url=firebase_user.get("avatar_url") or gh_user.get("avatar_url"),
                provider="github" if github_token else "google",
                github_login=gh_user.get("login"),
            )
        except Exception as exc:
            logger.warning("Could not persist user %s to Firestore: %s", uid, exc)

    user_info = (
        saved_user.model_dump(mode="json")
        if saved_user
        else (session.get("github_user") or session.get("user"))
    )
    return jsonify(
        {
            "ok": True,
            "authenticated": bool(session.get("github_token")),
            "user": user_info,
        }
    )


@bp.get("/me")
def get_current_user():
    """Retrieve the currently authenticated user's profile from Firestore."""
    user_sess = session.get("user") or {}
    uid = user_sess.get("uid")
    if not uid:
        gh_user = session.get("github_user")
        if gh_user:
            return jsonify({"authenticated": True, "user": gh_user})
        return jsonify({"authenticated": False, "user": None}), 401

    user = db.get_user(uid)
    if not user:
        return jsonify({"authenticated": True, "user": user_sess})

    return jsonify({"authenticated": True, "user": user.model_dump(mode="json")})


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


@bp.post("/logout")
def logout():
    """Clear all authenticated session data (Firebase user + GitHub token)."""
    session.pop("user", None)
    session.pop("github_token", None)
    session.pop("github_user", None)
    session.clear()
    return jsonify({"ok": True, "authenticated": False})


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
