"""Application configuration."""

import json
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    anthropic_api_key: str | None = Field(default=None)
    github_token: str | None = Field(default=None)
    github_app_id: str | None = Field(default=None)
    github_webhook_secret: str | None = Field(default=None)
    github_private_key: str | None = Field(default=None)
    github_check_run_name: str = Field(default="SignalReview")
    environment: str = Field(default="development")
    app_version: str = Field(default="0.1.0")
    cors_origins: str = Field(default="http://localhost:5173")

    @field_validator(
        "anthropic_api_key",
        "github_token",
        "github_app_id",
        "github_webhook_secret",
        "github_private_key",
        mode="before",
    )
    @classmethod
    def normalize_optional_secret(cls, value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped_value = value.strip()
            if not stripped_value:
                return None
            return stripped_value.replace("\\n", "\n")
        raise TypeError("Secret settings must be strings.")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def normalize_cors_origins(cls, value: object) -> str:
        if isinstance(value, list):
            return ",".join(str(item).strip() for item in value if str(item).strip())
        if isinstance(value, str):
            return value.strip()
        raise TypeError("CORS origins must be a comma-separated string.")

    def get_cors_origins(self) -> list[str]:
        """Return CORS origins as a normalized list."""

        stripped_value = self.cors_origins.strip()
        if stripped_value.startswith("["):
            try:
                decoded_value = json.loads(stripped_value)
            except json.JSONDecodeError:
                decoded_value = None
            if isinstance(decoded_value, list):
                return [str(item).strip() for item in decoded_value if str(item).strip()]

        return [origin.strip() for origin in stripped_value.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached application settings instance."""

    return Settings()
