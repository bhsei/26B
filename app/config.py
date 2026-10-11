from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./outliers.db"
    ai_provider: Literal["mock"] = "mock"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    max_image_bytes: int = Field(default=5 * 1024 * 1024, gt=0)
