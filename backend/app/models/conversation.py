from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ConversationState(BaseModel):
    """Root session record. All other tables FK to session_id."""

    session_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    channel: Literal["voice", "chat", "hybrid"] = "voice"
    sentiment: Optional[Literal["frustrated", "neutral", "satisfied", "urgent"]] = "neutral"
    turn_count: int = 0
    handoff_summary: Optional[str] = None


class CustomerInfo(BaseModel):
    """Verified customer identity and profile."""

    session_id: str
    verified: bool = False
    customer_id: Optional[str] = None
    name: Optional[str] = None
    tier: Optional[Literal["standard", "premium", "enterprise"]] = None
    phone: Optional[str] = None       # PII — mask in logs
    account_no: Optional[str] = None  # PII — mask in logs
