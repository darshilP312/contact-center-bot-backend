from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WorkingMemory(BaseModel):
    """Ephemeral in-turn execution state (Redis, TTL = session duration)."""

    session_id: str
    current_workflow: Optional[str] = None
    router_restarted: bool = False
    diagnostics_run: list = Field(default_factory=list)   # list of diagnostic IDs
    last_tool_result: dict = Field(default_factory=dict)  # JSONB
    pending_action: Optional[str] = None


class LongTermMemory(BaseModel):
    """Historical customer memory (PostgreSQL/FAISS, persistent)."""

    session_id: str
    previous_tickets: list = Field(default_factory=list)        # JSONB
    last_call_date: Optional[datetime] = None
    engineer_visit_history: list = Field(default_factory=list)  # JSONB
    known_issues: list = Field(default_factory=list)            # JSONB
