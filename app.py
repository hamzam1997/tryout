from datetime import timedelta
from pathlib import Path

from flask import Flask, jsonify, send_from_directory

from config import settings
from database import init_db
from logging_setup import configure_logging
from views.attempts import bp as attempts_bp
from views.auth import bp as auth_bp, require_login
from views.bottlenecks import bp as bottlenecks_bp
from views.ideas import bp as ideas_bp
from views.invitations import bp as invitations_bp
from views.meetings import bp as meetings_bp
from views.repositories import bp as repositories_bp
from views.workspaces import bp as workspaces_bp

# Written by the Dockerfile's build stage. Absent in local development, where
# Vite serves the frontend on its own port and proxies the API here.
FRONTEND_DIST = Path(__file__).resolve().parent / "frontend" / "dist"

configure_logging()

app = Flask(__name__, static_folder=None)
app.secret_key = settings.secret_key
app.config.update(
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=not settings.debug,  # Cloud Run is HTTPS; local dev is not
)
init_db()


app.before_request(require_login)
app.register_blueprint(auth_bp)
app.register_blueprint(meetings_bp)
app.register_blueprint(ideas_bp)
app.register_blueprint(repositories_bp)
app.register_blueprint(bottlenecks_bp)
app.register_blueprint(attempts_bp)
app.register_blueprint(workspaces_bp)
app.register_blueprint(invitations_bp)


@app.get("/health")
def health():
    return jsonify({"status": "ok", "ui": FRONTEND_DIST.is_dir()})


@app.get("/")
def index():
    if not FRONTEND_DIST.is_dir():
        return "tryout is alive"
    return send_from_directory(FRONTEND_DIST, "index.html")


@app.get("/<path:filename>")
def frontend_asset(filename: str):
    """Serve a built asset, falling back to index.html.

    Registered after the API blueprint, whose concrete rules take precedence.
    The fallback is so client-side routes still resolve once the app grows
    past one page.
    """
    if filename.startswith("api/") or not FRONTEND_DIST.is_dir():
        return jsonify({"error": "not found"}), 404

    if (FRONTEND_DIST / filename).is_file():
        return send_from_directory(FRONTEND_DIST, filename)
    return send_from_directory(FRONTEND_DIST, "index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.port, debug=settings.debug)
