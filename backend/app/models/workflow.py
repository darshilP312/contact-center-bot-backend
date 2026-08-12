from __future__ import annotations

from pydantic import BaseModel, Field


class WorkflowState(BaseModel):
    """Current workflow execution state."""

    session_id: str
    name: str | None = None              # e.g. "claim_filing"
    step: str | None = None              # e.g. "verify_documents"
    completed_steps: list = Field(default_factory=list)    # JSONB
    step_attempts: dict = Field(default_factory=dict)      # JSONB — step -> attempt count
    step_results: dict = Field(default_factory=dict)       # JSONB — step -> result payload
