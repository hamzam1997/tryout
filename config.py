import logging
import secrets
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Central access to credentials and tunables, loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # The MODEL_* settings below would otherwise collide with pydantic's
        # reserved "model_" attribute namespace.
        protected_namespaces=(),
    )

    # Gemini is reached through Vertex AI, which bills via Google Cloud and
    # still serves the 2.5 models that the AI Studio API retired for new keys.
    google_cloud_project: str = ""
    # "global" is the only location serving both the 2.5 and 3.x families;
    # regional endpoints such as us-central1 404 on the newer models.
    google_cloud_location: str = "global"

    secret_key: str = ""
    port: int = 8080
    debug: bool = Field(default=False, validation_alias="FLASK_DEBUG")

    database_path: Path = BASE_DIR / "tryout.db"

    model_extraction: str = "gemini-2.5-flash"
    model_onboarding: str = "gemini-2.5-flash"
    model_planning: str = "gemini-2.5-pro"
    model_coding: str = "gemini-2.5-pro"

    execution_timeout_seconds: int = Field(default=60, gt=0)

    @model_validator(mode="after")
    def _fill_secret_key(self) -> "Settings":
        if not self.secret_key:
            self.secret_key = secrets.token_urlsafe(32)
            logger.warning(
                "SECRET_KEY is not set; using a random key for this process. "
                "Sessions will not survive a restart or span multiple instances."
            )
        return self

    @property
    def has_project(self) -> bool:
        return bool(self.google_cloud_project)

    def require_project(self) -> str:
        """Return the Cloud project for Vertex calls, raising if unconfigured.

        Never fall back to the project Application Default Credentials infers:
        ADC reads it from the local gcloud config, which may point at an
        unrelated (and possibly production) project.
        """
        if not self.google_cloud_project:
            raise RuntimeError(
                "GOOGLE_CLOUD_PROJECT is not set. Add it to .env (see .env.example)."
            )
        return self.google_cloud_project


settings = Settings()

if not settings.has_project:
    logger.warning(
        "GOOGLE_CLOUD_PROJECT is not set; agent features will fail until it is "
        "configured."
    )
