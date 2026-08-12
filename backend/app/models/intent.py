from __future__ import annotations

from pydantic import BaseModel, Field


class IntentInfo(BaseModel):
    """Detected intent for the current turn."""

    session_id: str
    name: str | None = None                         # e.g. "file_claim", "policy_inquiry"
    confidence: float = 0.0
    entities: dict = Field(default_factory=dict)    # JSONB — extracted entities
    secondary_intents: list = Field(default_factory=list)  # JSONB — runner-up intents
