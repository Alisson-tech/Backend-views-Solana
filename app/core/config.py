"""
Application settings loaded from environment variables via pydantic-settings.
All API keys and sensitive configuration are managed here.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized settings loaded from .env file."""

    YOUTUBE_API_KEY: str

    # Extend with additional platform keys as needed:
    # INSTAGRAM_ACCESS_TOKEN: str = ""
    # TIKTOK_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


# Singleton instance used across the application
settings = Settings()  # type: ignore[call-arg]
