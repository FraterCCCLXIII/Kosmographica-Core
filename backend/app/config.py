from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven application settings."""

    database_url: str = Field(alias="DATABASE_URL")
    rabbitmq_url: str = Field(alias="RABBITMQ_URL")
    anthropic_api_key: str = Field(alias="ANTHROPIC_API_KEY")
    openai_api_key: str = Field(alias="OPENAI_API_KEY")
    embedding_provider: str = Field(default="openai", alias="EMBEDDING_PROVIDER")
    llm_provider: str = Field(default="anthropic", alias="LLM_PROVIDER")
    upload_dir: str = Field(default="uploads", alias="UPLOAD_DIR")
    dramatiq_dev_mode: bool = Field(default=False, alias="DRAMATIQ_DEV_MODE")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
