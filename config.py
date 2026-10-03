import logging
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
    # "global" serves both the 2.5 and 3.x families; regional endpoints do not.
    google_cloud_location: str = "global"

    port: int = 8080
    debug: bool = Field(default=False, validation_alias="FLASK_DEBUG")

    # Database settings: Google Cloud Firestore
    firestore_database: str = Field(default="(default)", validation_alias="FIRESTORE_DATABASE")

    model_extraction: str = "gemini-2.5-flash"
    model_onboarding: str = "gemini-2.5-flash"
    model_planning: str = "gemini-2.5-pro"
    model_coding: str = "gemini-2.5-pro"

    execution_timeout_seconds: int = Field(default=60, gt=0)

    # Firebase settings: loaded from environment / Secret Manager
    firebase_api_key: str = Field(default="AIzaSyCAst4nJNYaxCp_h5-C0D0e2QSh6mDi6y0", validation_alias="FIREBASE_API_KEY")
    firebase_auth_domain: str = Field(default="project-d8ffc1c1-61f2-4aef-9ab.firebaseapp.com", validation_alias="FIREBASE_AUTH_DOMAIN")
    firebase_project_id: str = Field(default="project-d8ffc1c1-61f2-4aef-9ab", validation_alias="FIREBASE_PROJECT_ID")
    firebase_storage_bucket: str = Field(default="project-d8ffc1c1-61f2-4aef-9ab.firebasestorage.app", validation_alias="FIREBASE_STORAGE_BUCKET")
    firebase_messaging_sender_id: str = Field(default="228085742413", validation_alias="FIREBASE_MESSAGING_SENDER_ID")
    firebase_app_id: str = Field(default="1:228085742413:web:80180bf01b38db40acd504", validation_alias="FIREBASE_APP_ID")

    # Session and GitHub OAuth settings
    secret_key: str = "tryout-dev-secret-key-change-in-prod"
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

if not settings.google_cloud_project:
    logger.warning("GOOGLE_CLOUD_PROJECT is not set; agent features will fail.")
