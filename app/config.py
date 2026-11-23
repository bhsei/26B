from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./outliers.db"
    ai_provider: Literal["mock"] = "mock"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    max_image_bytes: int = Field(default=5 * 1024 * 1024, gt=0)

    # Local development uses HTTP. Set AUTH_COOKIE_SECURE=true behind HTTPS.
    auth_cookie_secure: bool = False
    auth_session_ttl_seconds: int = Field(default=8 * 60 * 60, ge=60, le=7 * 86400)
    auth_session_idle_seconds: int = Field(default=60 * 60, ge=60, le=86400)
    auth_login_max_attempts: int = Field(default=10, ge=1, le=1000)
    auth_login_window_seconds: int = Field(default=60, ge=1, le=3600)
