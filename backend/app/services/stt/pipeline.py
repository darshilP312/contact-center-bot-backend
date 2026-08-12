from __future__ import annotations

import asyncio
import time
from typing import AsyncGenerator, Callable

from app.core.logging import get_logger
from app.services.stt.vad import SileroVAD
from app.services.stt.whisper_stt import WhisperSTT

logger = get_logger("stt.pipeline")

PARTIAL_EMIT_INTERVAL_MS = 500  # Emit partial transcript every 500ms


class STTPipeline:
    """
    Orchestrates VAD → STT pipeline for streaming audio.

    Flow:
    1. Receives raw PCM frames from WebSocket
    2. Passes each 30ms frame to Silero VAD
    3. On speech_end: sends accumulated audio to faster-whisper
    4. Emits partial transcript estimates every 500ms during active speech
    5. Emits final transcript when VAD signals end of speech

    Args:
        stt: WhisperSTT instance.
        language: Language code for STT.
        on_partial: Callback for partial transcripts (called every 500ms during speech).
        on_final: Callback for final transcripts (called after VAD silence detection).
    """

    def __init__(
        self,
        stt: WhisperSTT,
        language: str = "en",
        on_partial: Callable[[str], None] | None = None,
        on_final: Callable[[str], None] | None = None,
    ) -> None:
        self.stt = stt
        self.language = language if language != "auto" else None
        self.on_partial = on_partial
        self.on_final = on_final
        self.vad = SileroVAD()
        self._partial_buffer: list[bytes] = []
        self._last_partial_time = 0.0
        self._is_speech_active = False

    async def _emit_partial(self, speech_bytes: bytes) -> None:
        """Transcribe current speech buffer and emit partial transcript."""
        if not speech_bytes or len(speech_bytes) < 960:
            return
        try:
            text = await self.stt.transcribe(speech_bytes, language=self.language)
            if text and self.on_partial:
                self.on_partial(text)
        except Exception as e:
            logger.warning("Partial transcription failed", node="stt.pipeline", error=str(e))

    async def _on_speech_end_async(self, audio_bytes: bytes) -> None:
        """Handle VAD speech end: run final STT and emit result."""
        if not audio_bytes:
            return
        try:
            text = await self.stt.transcribe(audio_bytes, language=self.language)
            if text and self.on_final:
                self.on_final(text)
                logger.info(
                    "Final transcript emitted",
                    node="stt.pipeline",
                    text=text[:100],
                )
        except Exception as e:
            logger.error("Final transcription failed", node="stt.pipeline", error=str(e))

    async def process(self, audio_generator: AsyncGenerator[bytes, None]) -> None:
        """
        Process a stream of raw PCM audio chunks.

        Buffers audio into VAD frames (30ms / 960 bytes) and processes each frame.
        Handles partial emission on a 500ms timer and final emission on VAD silence.

        Args:
            audio_generator: Async generator yielding raw PCM bytes.
        """
        if not self.vad.is_loaded:
            await self.vad.load()

        frame_buffer = b""
        frame_size = 960  # 30ms @ 16kHz 16-bit mono
        accumulated_speech: list[bytes] = []
        pending_final: asyncio.Task | None = None

        def on_speech_end_sync(audio_bytes: bytes) -> None:
            """Synchronous bridge to async final transcript handler."""
            nonlocal pending_final
            pending_final = asyncio.create_task(self._on_speech_end_async(audio_bytes))

        async for chunk in audio_generator:
            frame_buffer += chunk

            # Process complete 30ms frames
            while len(frame_buffer) >= frame_size:
                frame = frame_buffer[:frame_size]
                frame_buffer = frame_buffer[frame_size:]

                result = self.vad.process_frame(frame, on_speech_end=on_speech_end_sync)

                if result["is_speech"]:
                    self._is_speech_active = True
                    accumulated_speech.append(frame)

                    # Partial transcript every 500ms
                    now = time.monotonic() * 1000
                    if now - self._last_partial_time >= PARTIAL_EMIT_INTERVAL_MS:
                        self._last_partial_time = now
                        speech_so_far = b"".join(accumulated_speech)
                        asyncio.create_task(self._emit_partial(speech_so_far))
                elif result.get("is_speech_end"):
                    self._is_speech_active = False
                    accumulated_speech = []

        # Process any remaining buffered audio
        if frame_buffer and self._is_speech_active:
            remaining = b"".join(accumulated_speech) + frame_buffer
            await self._on_speech_end_async(remaining)
