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

    database_path: Path = BASE_DIR / "tryout.db"

    model_extraction: str = "gemini-2.5-flash"
    model_onboarding: str = "gemini-2.5-flash"
    model_planning: str = "gemini-2.5-pro"
    model_coding: str = "gemini-2.5-pro"

    execution_timeout_seconds: int = Field(default=60, gt=0)

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
