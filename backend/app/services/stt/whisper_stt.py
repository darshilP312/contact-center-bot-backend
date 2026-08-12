from __future__ import annotations

import asyncio
import os
from typing import AsyncGenerator

from app.core.logging import get_logger

logger = get_logger("stt.whisper")

SAMPLE_RATE = 16000


class WhisperSTT:
    """
    faster-whisper streaming STT service.

    Wraps CTranslate2-optimised Whisper for low-latency speech-to-text.
    Runs inference in a thread pool to avoid blocking the asyncio event loop.
    """

    def __init__(
        self,
        model_size: str = "base",
        model_dir: str = ".models/whisper",
        compute_type: str = "int8",
        device: str = "cpu",
    ) -> None:
        self.model_size = model_size
        self.model_dir = os.path.abspath(model_dir)
        self.compute_type = compute_type
        self.device = device
        self._model = None
        self.is_loaded = False

    async def warm_up(self) -> None:
        """Load the Whisper model (downloads on first run, cached thereafter)."""
        loop = asyncio.get_event_loop()

        def _load():
            from faster_whisper import WhisperModel

            os.makedirs(self.model_dir, exist_ok=True)
            try:
                model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                    download_root=self.model_dir,
                )
                return model
            except Exception as e:
                logger.warning(
                    f"Could not load faster-whisper model '{self.model_size}': {e}",
                    node="stt.whisper",
                )
                return None

        self._model = await loop.run_in_executor(None, _load)
        self.is_loaded = self._model is not None
        if self.is_loaded:
            logger.info(
                "faster-whisper model loaded",
                node="stt.whisper",
                model_size=self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
        else:
            logger.warning(
                "faster-whisper model unavailable",
                node="stt.whisper",
            )

    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str | None = None,
        task: str = "transcribe",
    ) -> str:
        """
        Transcribe audio bytes to text.

        Args:
            audio_bytes: 16-bit PCM audio at 16kHz (mono).
            language: ISO 639-1 language code, or None for auto-detection.
            task: "transcribe" or "translate" (translate to English).

        Returns:
            Transcribed text string.
        """
        if not self.is_loaded or self._model is None:
            logger.warning("Whisper model not loaded. Returning empty string.", node="stt.whisper")
            return ""

        loop = asyncio.get_event_loop()

        def _transcribe():
            import numpy as np

            # Convert bytes to float32 numpy array
            audio_array = (
                np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            )

            segments, info = self._model.transcribe(
                audio_array,
                language=language,
                task=task,
                beam_size=5,
                best_of=5,
                temperature=0.0,
                vad_filter=False,  # We use our own VAD
                word_timestamps=False,
            )

            text = " ".join(segment.text.strip() for segment in segments)
            return text.strip(), info.language

        text, detected_lang = await loop.run_in_executor(None, _transcribe)

        logger.info(
            "Transcription complete",
            node="stt.whisper",
            text_length=len(text),
            detected_language=detected_lang,
        )

        return text

    async def transcribe_stream(
        self,
        audio_bytes: bytes,
        language: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Transcribe audio and yield text segments as they are produced.

        For the current faster-whisper model, this returns the full transcription
        in one shot. Future versions will support true streaming.

        Args:
            audio_bytes: Audio to transcribe.
            language: Language override.

        Yields:
            Text segments.
        """
        text = await self.transcribe(audio_bytes, language=language)
        if text:
            yield text
