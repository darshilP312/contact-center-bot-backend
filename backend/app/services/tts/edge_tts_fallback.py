from __future__ import annotations

import asyncio
import io
import wave
from typing import AsyncGenerator

from app.core.logging import get_logger

logger = get_logger("tts.edge_tts")


class EdgeTTSFallback:
    """
    Microsoft Edge TTS fallback — free, no API key required.

    Uses the edge-tts Python package which calls the same TTS service
    as Microsoft Edge's Read Aloud feature. No account or API key needed.

    Available voices: en-IN-NeerjaNeural, en-US-JennyNeural,
    en-GB-SoniaNeural, hi-IN-SwaraNeural, etc.
    """

    def __init__(self, default_voice: str = "en-IN-NeerjaNeural") -> None:
        self.default_voice = default_voice
        self.is_loaded = True  # No model to load for edge-tts

    async def warm_up(self) -> None:
        """Validate edge-tts is installed."""
        try:
            import edge_tts  # noqa: F401

            logger.info("edge-tts fallback ready", node="tts.edge_tts", voice=self.default_voice)
        except ImportError:
            logger.error(
                "edge-tts not installed. Run: pip install edge-tts",
                node="tts.edge_tts",
            )
            self.is_loaded = False

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        speed: float = 1.0,
    ) -> AsyncGenerator[bytes, None]:
        """
        Synthesise text using edge-tts and yield audio chunks.

        Args:
            text: Text to synthesise.
            voice: Voice override.
            speed: Speed multiplier (edge-tts uses rate % offset).

        Yields:
            MP3 audio bytes in chunks.
        """
        import edge_tts

        voice_id = voice or self.default_voice

        # Convert speed multiplier to edge-tts rate string
        # edge-tts rate: "+0%" = normal, "+25%" = 25% faster, "-25%" = slower
        rate_offset = int((speed - 1.0) * 100)
        rate_str = f"+{rate_offset}%" if rate_offset >= 0 else f"{rate_offset}%"

        try:
            communicate = edge_tts.Communicate(text, voice=voice_id, rate=rate_str)

            buffer = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buffer.extend(chunk["data"])

            # Yield in 4KB chunks
            audio_bytes = bytes(buffer)
            chunk_size = 4096
            for i in range(0, len(audio_bytes), chunk_size):
                yield audio_bytes[i: i + chunk_size]

        except Exception as e:
            logger.error(
                "edge-tts synthesis failed",
                node="tts.edge_tts",
                error=str(e),
                voice=voice_id,
            )
            raise
