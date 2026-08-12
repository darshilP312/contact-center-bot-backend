"""
config.py — Application settings loaded from environment variables.
All secrets and configuration flow through this module.
No hardcoded strings in any other file.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings via pydantic-settings (reads from .env)."""

    # ── LLM ──────────────────────────────────────────────────────────────────
    openai_api_key: str = Field("", validation_alias="OPENAI_API_KEY")
    llm_model: str = Field("gpt-4o-mini", env="LLM_MODEL")
    understand_model: str = Field("gpt-4o-mini", env="UNDERSTAND_MODEL")
    plan_model: str = Field("gpt-4o", env="PLAN_MODEL")
    generate_model: str = Field("gpt-4o-mini", env="GENERATE_MODEL")

    # ── Speech ────────────────────────────────────────────────────────────────
    azure_speech_key: str = Field("", env="AZURE_SPEECH_KEY")
    azure_speech_region: str = Field("eastus", env="AZURE_SPEECH_REGION")
    deepgram_api_key: str = Field("", env="DEEPGRAM_API_KEY")
    stt_provider: str = Field("azure", env="STT_PROVIDER")

    # ── Storage ───────────────────────────────────────────────────────────────
    redis_url: str = Field("redis://localhost:6379", env="REDIS_URL")
    postgres_url: str = Field(
        "postgresql://ccuser:ccpass@localhost:5432/contact_centre",
        env="POSTGRES_URL"
    )

    # ── Observability ─────────────────────────────────────────────────────────
    langfuse_secret_key: str = Field("", env="LANGFUSE_SECRET_KEY")
    langfuse_public_key: str = Field("", env="LANGFUSE_PUBLIC_KEY")
    langfuse_host: str = Field("https://cloud.langfuse.com", env="LANGFUSE_HOST")

    # ── App ───────────────────────────────────────────────────────────────────
    app_env: str = Field("development", env="APP_ENV")
    log_level: str = Field("DEBUG", env="LOG_LEVEL")
    cors_origins: str = Field("http://localhost:5173", env="CORS_ORIGINS")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
