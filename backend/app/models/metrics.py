from __future__ import annotations

from pydantic import BaseModel, Field


class ObservabilityMetrics(BaseModel):
    """Per-session accumulated performance metrics."""

    session_id: str
    turn_latencies_ms: dict = Field(default_factory=dict)  # JSONB — turn_id -> ms
    total_tokens_used: int = 0
    total_cost: float = 0.0
    tool_calls_made: int = 0
