from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables.

    All secrets (LLM_API_KEY, REDIS_URL, etc.) are required — the app will
    fail fast at startup if they are missing. Non-sensitive settings have
    safe defaults.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── LLM Configuration ─────────────────────────────────────────────────────
    LLM_BASE_URL: str
    LLM_API_KEY: str
    LLM_MODEL: str
    LLM_API_VERSION: Optional[str] = None  # Azure OpenAI only
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 1024
    LLM_TIMEOUT_SECONDS: int = 30

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str
    REDIS_SESSION_TTL_SECONDS: int = 3600

    # ── STT (faster-whisper) ─────────────────────────────────────────────────
    STT_MODEL_SIZE: Literal["tiny", "base", "small", "medium", "large-v3"] = "base"
    STT_MODEL_DIR: str = ".models/whisper"
    STT_LANGUAGES: str = "en,hi,ta,te,kn,mr,bn"
    STT_COMPUTE_TYPE: Literal["float32", "float16", "int8"] = "int8"
    STT_DEVICE: Literal["cpu", "cuda"] = "cpu"

    # ── TTS ───────────────────────────────────────────────────────────────────
    TTS_PROVIDER: Literal["kokoro", "edge_tts"] = "kokoro"
    TTS_KOKORO_MODEL_DIR: str = ".models/kokoro"
    TTS_DEFAULT_VOICE: str = "af_heart"
    TTS_EDGE_VOICE: str = "en-IN-NeerjaNeural"
    TTS_OUTPUT_FORMAT: Literal["wav", "pcm"] = "wav"

    # ── RAG / Vector Store ────────────────────────────────────────────────────
    VECTOR_STORE: Literal["faiss", "pgvector"] = "faiss"
    EMBEDDING_PROVIDER: Literal["local", "openai"] = "local"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    POSTGRES_URL: Optional[str] = None
    RAG_TOP_K: int = 5
    FAISS_INDEX_DIR: str = "faiss_indices"

    # ── Langfuse (Optional) ───────────────────────────────────────────────────
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_HOST: Optional[str] = "https://cloud.langfuse.com"

    # ── Application ───────────────────────────────────────────────────────────
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_FORMAT: Literal["json", "console"] = "console"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    FRONTEND_PORT: int = 5173
    FRONTEND_ENABLED: bool = True
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    MAX_TURNS_BEFORE_ESCALATION: int = 10
    PLANNER_MAX_LOOP_COUNT: int = 3
    DOMAINS_DIR: str = "domains"
    SESSION_SECRET_KEY: Optional[str] = None

    @property
    def stt_language_list(self) -> list[str]:
        """Parse comma-separated language codes into a list."""
        return [lang.strip() for lang in self.STT_LANGUAGES.split(",")]

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def langfuse_enabled(self) -> bool:
        """Langfuse is enabled only if both keys are configured."""
        return bool(self.LANGFUSE_SECRET_KEY and self.LANGFUSE_PUBLIC_KEY)

    @property
    def pgvector_enabled(self) -> bool:
        """pgvector is enabled only if POSTGRES_URL is set and VECTOR_STORE=pgvector."""
        return self.VECTOR_STORE == "pgvector" and bool(self.POSTGRES_URL)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return cached Settings singleton.

    Using lru_cache ensures settings are only loaded once at startup.
    In tests, call get_settings.cache_clear() to reset.
    """
    return Settings()
