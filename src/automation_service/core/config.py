"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8080
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # CORS
    CORS_ORIGINS: list[str] = Field(default=["*"])

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # Browser settings
    BROWSER_HEADLESS: bool = True
    BROWSER_TIMEOUT: int = 30000  # milliseconds
    BROWSER_SLOW_MO: int = 0  # milliseconds between actions

    # Club Virtual settings
    CLUB_VIRTUAL_BASE_URL: str = "https://clubvirtual-asd.org.mx"
    CLUB_VIRTUAL_LOGIN_PATH: str = "/login/auth"
    CLUB_VIRTUAL_SELECT_CLUB_PATH: str = "/valida/selecciona-club"

    # Session settings
    SESSION_STORAGE_PATH: str = "./sessions"
    SESSION_TTL_HOURS: int = 24

    # Redis (optional, for session caching)
    REDIS_URL: str | None = None

    # Screenshots
    SCREENSHOTS_PATH: str = "./screenshots"
    SCREENSHOTS_ENABLED: bool = True


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
