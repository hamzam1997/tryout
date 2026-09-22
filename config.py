import logging
import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

logger = logging.getLogger(__name__)


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("%s=%r is not an integer, falling back to %d", key, raw, default)
        return default


class Settings(BaseModel):
    """Central access to credentials and tunables, loaded from the environment."""

    gemini_api_key: str = ""

    port: int = 8080
    debug: bool = False
    secret_key: str = "tryout-dev-secret-key-2026"

    database_path: str = "tryout.db"

    model_extraction: str = "gemini-2.5-flash"
    model_onboarding: str = "gemini-2.5-flash"
    model_planning: str = "gemini-2.5-pro"
    model_coding: str = "gemini-2.5-pro"

    execution_timeout_seconds: int = Field(default=60, gt=0)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            gemini_api_key=_env("GEMINI_API_KEY"),
            port=_env_int("PORT", 8080),
            debug=_env("FLASK_DEBUG", "0") not in ("", "0", "false", "False"),
            secret_key=_env("SECRET_KEY", "tryout-dev-secret-key-2026"),
            database_path=_env("DATABASE_PATH", "tryout.db"),
            model_extraction=_env("MODEL_EXTRACTION", "gemini-2.5-flash"),
            model_onboarding=_env("MODEL_ONBOARDING", "gemini-2.5-flash"),
            model_planning=_env("MODEL_PLANNING", "gemini-2.5-pro"),
            model_coding=_env("MODEL_CODING", "gemini-2.5-pro"),
            execution_timeout_seconds=_env_int("EXECUTION_TIMEOUT_SECONDS", 60),
        )

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


settings = Settings.from_env()

if not settings.has_gemini_key:
    logger.warning(
        "GEMINI_API_KEY is not set; agent features will fail until it is configured."
    )
