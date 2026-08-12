from __future__ import annotations

import asyncio
import os
from typing import AsyncGenerator

from app.core.logging import get_logger

logger = get_logger("tts.kokoro")


class KokoroTTS:
    """
    Kokoro ONNX TTS — primary open-source text-to-speech engine.

    Runs locally using ONNX Runtime (no API key, no internet required after
    model download). Streams synthesised audio sentence-by-sentence.

    Voices: af_heart (default), af_bella, am_adam, am_michael, bf_emma,
            bm_george, bm_lewis — and Indic voices where available.
    """

    def __init__(
        self,
        model_dir: str = ".models/kokoro",
        default_voice: str = "af_heart",
    ) -> None:
        self.model_dir = os.path.abspath(model_dir)
        self.default_voice = default_voice
        self._kokoro = None
        self.is_loaded = False

    async def warm_up(self) -> None:
        """Load Kokoro ONNX model (downloads on first run, ~300MB)."""
        loop = asyncio.get_event_loop()

        def _load():
            try:
                from kokoro_onnx import Kokoro

                os.makedirs(self.model_dir, exist_ok=True)
                model_path = os.path.join(self.model_dir, "kokoro-v0_19.onnx")
                voices_path = os.path.join(self.model_dir, "voices.bin")

                # Download models if not present
                if not os.path.exists(model_path) or not os.path.exists(voices_path):
                    logger.info(
                        "Downloading Kokoro TTS models (~300MB)...",
                        node="tts.kokoro",
                    )
                    Kokoro.download(model_dir=self.model_dir)

                return Kokoro(model_path, voices_path)
            except ImportError:
                logger.warning(
                    "kokoro-onnx not installed. TTS will use edge-tts fallback.",
                    node="tts.kokoro",
                )
                return None

        self._kokoro = await loop.run_in_executor(None, _load)
        self.is_loaded = self._kokoro is not None

        if self.is_loaded:
            logger.info("Kokoro TTS loaded", node="tts.kokoro", voice=self.default_voice)
        else:
            logger.warning("Kokoro TTS unavailable — will fallback to edge-tts", node="tts.kokoro")

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        speed: float = 1.0,
    ) -> AsyncGenerator[bytes, None]:
        """
        Synthesise text to speech, yielding audio chunks.

        Args:
            text: Text to synthesise.
            voice: Voice ID override (defaults to self.default_voice).
            speed: Playback speed multiplier (0.5–2.0).

        Yields:
            Audio bytes (WAV format with header on first chunk, raw PCM thereafter).
        """
        if not self.is_loaded or self._kokoro is None:
            raise RuntimeError("Kokoro model not loaded")

        loop = asyncio.get_event_loop()
        voice_id = voice or self.default_voice

        def _synthesize():
            samples, sample_rate = self._kokoro.create(
                text,
                voice=voice_id,
                speed=speed,
                lang="en-us",
            )
            return samples, sample_rate

        try:
            samples, sample_rate = await loop.run_in_executor(None, _synthesize)

            # Convert float samples to 16-bit WAV bytes
            import io
            import wave

            import numpy as np

            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(sample_rate)
                pcm = (samples * 32767).astype(np.int16).tobytes()
                wf.writeframes(pcm)

            audio_bytes = buffer.getvalue()

            # Yield in 4KB chunks for streaming
            chunk_size = 4096
            for i in range(0, len(audio_bytes), chunk_size):
                yield audio_bytes[i: i + chunk_size]

        except Exception as e:
            logger.error("Kokoro synthesis failed", node="tts.kokoro", error=str(e))
            raise
