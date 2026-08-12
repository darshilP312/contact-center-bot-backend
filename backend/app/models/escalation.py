from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.conversation import CustomerInfo
from app.models.flags import SessionFlags
from app.models.intent import IntentInfo
from app.models.workflow import WorkflowState


class EscalationSummary(BaseModel):
    """Complete context payload for human agent handoff."""

    session_id: str
    customer_info: CustomerInfo
    intent: IntentInfo
    workflow: WorkflowState
    flags: SessionFlags
    final_sentiment: str
    escalation_reason: str
    transcript_summary: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
