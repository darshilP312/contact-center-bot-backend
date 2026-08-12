from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class AudioPayload(BaseModel):
    """Binary audio frame envelope."""

    session_id: str
    sequence_number: int
    timestamp_ms: int
    audio_format: Literal["pcm_16khz_16bit_mono"] = "pcm_16khz_16bit_mono"
    data: bytes

    model_config = {"arbitrary_types_allowed": True}
