from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/command_center"
    redis_url: str = "redis://localhost:6379/0"
    sarvam_api_key: str = "your_sarvam_api_key_here"
    groq_api_key: str = "your_groq_api_key_here"
    secret_key: str = "command_center_secret_key_change_in_prod"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    log_level: str = "INFO"

    # Optional Sarvam configurations
    sarvam_stt_url: str = "https://api.sarvam.ai/speech-to-text"
    sarvam_tts_url: str = "https://api.sarvam.ai/text-to-speech"
    sarvam_stt_model: str = "saarika:v2.5"
    sarvam_tts_model: str = "bulbul:v3"
    sarvam_tts_speaker: str = "ritu"
    sarvam_stt_language_code: str = "en-IN"
    sarvam_tts_pace: float = 1.0

    # Optional Groq configurations
    groq_model: str = "groq/compound-mini"
    groq_url: str = "https://api.groq.com/openai/v1/chat/completions"

    # Server & Audio Settings
    host: str = "0.0.0.0"
    port: int = 8000
    audio_sample_rate: int = 16000
    audio_channels: int = 1
    enable_mock_fallback: bool = True

    # ── Billing / Refund configuration ────────────────────────────────────────
    refund_threshold_amount: float = 5000.0   # INR
    refund_currency: str = "INR"
    billing_late_fee_amount: float = 100.0    # INR added after grace period
    billing_grace_days: int = 7               # days after due date before late fee
    invoice_number_prefix: str = "INV"
    refund_number_prefix: str = "REF"
    refund_sla_hours: int = 48                # SLA for human review of threshold refunds

    # ── Scheduling configuration ───────────────────────────────────────────────
    appointment_number_prefix: str = "APT"
    scheduling_default_slot_mins: int = 30      # default appointment duration
    scheduling_max_future_days: int = 30        # how far ahead bookings are allowed
    scheduling_callback_sla_mins: int = 15      # target: agent calls back within N minutes
    scheduling_max_concurrent_sessions: int = 3 # default agent capacity


    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
