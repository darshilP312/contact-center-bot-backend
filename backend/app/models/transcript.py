from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class TranscriptEntry(BaseModel):
    """Single turn in the conversation transcript."""

    id: Optional[int] = None  # auto-increment PK in DB
    session_id: str
    role: Literal["customer", "agent", "system"]
    text: str
    ts: datetime = Field(default_factory=datetime.utcnow)
    rag_citations: list = Field(default_factory=list)  # JSONB — source refs if RAG used
