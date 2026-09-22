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

    gemini_api_key: str = ""
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
    def has_gemini_key(self) -> bool:
        return bool(self.gemini_api_key)

    def require_gemini_key(self) -> str:
        """Return the API key, raising if it was never configured.

        Call this from agent code paths so the app still boots without a key.
        """
        if not self.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Add it to .env (see .env.example)."
            )
        return self.gemini_api_key


settings = Settings()

if not settings.has_gemini_key:
    logger.warning(
        "GEMINI_API_KEY is not set; agent features will fail until it is configured."
    )
