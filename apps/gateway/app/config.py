from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ollama_base_url: str = "http://ollama:11434"
    default_model: str = "mistral:7b"
    ready_check_timeout_seconds: float = 2.0
    models_timeout_seconds: float = 10.0
    chat_timeout_seconds: float = 120.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
