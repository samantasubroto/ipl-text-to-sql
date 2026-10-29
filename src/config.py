"""Typed settings loaded from the .env file in the project root."""
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    llm_provider: Literal["openai", "gemini"] = "openai"

    openai_api_key: str | None = None
    openai_model: str | None = None

    gemini_api_key: str | None = None
    gemini_model: str | None = None


def get_settings() -> Settings:
    return Settings()
