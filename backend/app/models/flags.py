from __future__ import annotations

from pydantic import BaseModel


class SessionFlags(BaseModel):
    """Boolean flags tracking key session events."""

    session_id: str
    ticket_created: bool = False
    engineer_booked: bool = False
    escalated: bool = False
    awaiting_approval: bool = False
    refund_triggered: bool = False
    rag_used: bool = False
    barge_in_detected: bool = False
