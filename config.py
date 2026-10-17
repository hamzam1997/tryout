import logging
import secrets
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Application settings, loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # MODEL_* fields collide with pydantic's reserved "model_" namespace.
        protected_namespaces=(),
    )

    google_cloud_project: str = ""
    # "global" serves every current Gemini model; regional endpoints do not.
    google_cloud_location: str = "global"

    port: int = 8080
    # Seed demo history into each new workspace (SEED_DEMO_DATA=1). Off by default.
    seed_demo_data: bool = False
    # "Continue as evaluator" on the landing page (EVALUATOR_LOGIN=1): a throwaway
    # account with a seeded workspace, for judges who can't use Google or GitHub sign-in.
    evaluator_login: bool = False
    # Lets attempts on the demo repo open real pull requests for users with no GitHub
    # connection, i.e. evaluators (DEMO_GITHUB_TOKEN). Scope it to the demo repo only.
    demo_github_token: str = ""
    debug: bool = Field(default=False, validation_alias="FLASK_DEBUG")

    # Database settings: Google Cloud Firestore
    firestore_database: str = Field(default="(default)", validation_alias="FIRESTORE_DATABASE")

    model_extraction: str = "gemini-3.8-flash"
    model_onboarding: str = "gemini-3.8-flash"
    model_planning: str = "gemini-3.8-flash"
    model_coding: str = "gemini-3.8-flash"

    execution_timeout_seconds: int = Field(default=60, gt=0)

    # Firebase settings: loaded from environment / Secret Manager
    firebase_api_key: str = Field(default="", validation_alias="FIREBASE_API_KEY")
    firebase_auth_domain: str = Field(default="", validation_alias="FIREBASE_AUTH_DOMAIN")
    firebase_project_id: str = Field(default="", validation_alias="FIREBASE_PROJECT_ID")
    firebase_storage_bucket: str = Field(default="", validation_alias="FIREBASE_STORAGE_BUCKET")
    firebase_messaging_sender_id: str = Field(default="", validation_alias="FIREBASE_MESSAGING_SENDER_ID")
    firebase_app_id: str = Field(default="", validation_alias="FIREBASE_APP_ID")

    # Session and GitHub OAuth settings
    secret_key: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = ""
    repos_cache_dir: Path = BASE_DIR / "cloned_repos"

    def require_project(self) -> str:
        """Return the Cloud project, raising if it is not configured."""
        if not self.google_cloud_project:
            raise RuntimeError(
                "GOOGLE_CLOUD_PROJECT is not set. Add it to .env (see .env.example)."
            )
        return self.google_cloud_project


settings = Settings()

if not settings.secret_key:
    if not settings.debug:
        raise RuntimeError("SECRET_KEY is not set. Add it to .env (see .env.example).")
    # Debug only: a throwaway key, so sessions and stored GitHub tokens reset on restart.
    settings.secret_key = secrets.token_hex(32)
    logger.warning("SECRET_KEY is not set; using a random key for this debug run.")

if not settings.google_cloud_project:
    logger.warning("GOOGLE_CLOUD_PROJECT is not set; agent features will fail.")
