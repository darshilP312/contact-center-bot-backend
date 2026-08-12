from __future__ import annotations

import asyncio
from typing import Callable

import numpy as np

from app.core.logging import get_logger

logger = get_logger("stt.vad")

# VAD configuration constants
SAMPLE_RATE = 16000
FRAME_SIZE_MS = 30  # Silero VAD works in 30ms frames
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_SIZE_MS / 1000)  # 480 samples
VAD_THRESHOLD = 0.5
SILENCE_FRAMES_TO_END = 10  # ~300ms of silence ends a speech segment


class SileroVAD:
    """
    Silero VAD wrapper for voice activity detection.

    Processes 30ms PCM 16kHz frames and emits speech_start / speech_end events.
    Used to gate audio to faster-whisper (avoids transcribing silence) and
    detect barge-in (customer speaks while TTS is playing).
    """

    def __init__(self) -> None:
        self._model = None
        self._is_speaking = False
        self._silence_frame_count = 0
        self._speech_buffer: list[bytes] = []
        self.is_loaded = False

    async def load(self) -> None:
        """Load Silero VAD model from local package (no GitHub download required)."""
        loop = asyncio.get_event_loop()

        def _load_model():
            try:
                # Use local silero-vad package (already installed via requirements.txt)
                from silero_vad import load_silero_vad
                model = load_silero_vad()
                return model
            except (ImportError, Exception) as e:
                logger.warning(
                    f"silero_vad package load failed ({e}), trying torch.hub fallback",
                    node="stt.vad",
                )
                try:
                    import torch
                    import os
                    # Disable GitHub validation to avoid rate-limit KeyError
                    os.environ.setdefault("TORCH_HUB_DIR", ".models/torch_hub")
                    model, utils = torch.hub.load(
                        repo_or_dir="snakers4/silero-vad",
                        model="silero_vad",
                        force_reload=False,
                        trust_repo=True,
                        skip_validation=True,
                    )
                    return model
                except Exception as e2:
                    logger.warning(
                        f"torch.hub VAD load also failed ({e2}). VAD disabled — passing all audio to STT.",
                        node="stt.vad",
                    )
                    return None

        self._model = await loop.run_in_executor(None, _load_model)
        self.is_loaded = self._model is not None
        if self.is_loaded:
            logger.info("Silero VAD model loaded", node="stt.vad")
        else:
            logger.warning("Silero VAD unavailable — all audio passed to STT", node="stt.vad")

    def _pcm_bytes_to_tensor(self, pcm_bytes: bytes):
        """Convert raw 16-bit PCM bytes to float32 tensor in [-1, 1] range."""
        import torch

        samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        return torch.from_numpy(samples)

    def _get_speech_prob(self, audio_tensor) -> float:
        """Run inference and return speech probability for a 30ms frame."""
        import torch

        with torch.no_grad():
            prob = self._model(audio_tensor, SAMPLE_RATE).item()
        return prob

    def process_frame(
        self,
        pcm_frame: bytes,
        on_speech_start: Callable[[], None] | None = None,
        on_speech_end: Callable[[bytes], None] | None = None,
    ) -> dict:
        """
        Process a 30ms PCM audio frame.

        Args:
            pcm_frame: 30ms of 16-bit PCM audio (960 bytes).
            on_speech_start: Callback when speech begins.
            on_speech_end: Callback when speech ends, receives accumulated audio bytes.

        Returns:
            dict with keys: is_speech (bool), probability (float), is_speech_end (bool).
        """
        if not self.is_loaded or self._model is None:
            return {"is_speech": True, "probability": 1.0, "is_speech_end": False}

        # Pad or trim frame to exact size
        expected_bytes = FRAME_SAMPLES * 2  # 16-bit = 2 bytes per sample
        if len(pcm_frame) < expected_bytes:
            pcm_frame = pcm_frame + b"\x00" * (expected_bytes - len(pcm_frame))
        elif len(pcm_frame) > expected_bytes:
            pcm_frame = pcm_frame[:expected_bytes]

        tensor = self._pcm_bytes_to_tensor(pcm_frame)
        prob = self._get_speech_prob(tensor)
        is_speech = prob >= VAD_THRESHOLD
        is_speech_end = False

        if is_speech:
            if not self._is_speaking:
                self._is_speaking = True
                self._speech_buffer = []
                self._silence_frame_count = 0
                if on_speech_start:
                    on_speech_start()
                logger.debug("Speech start detected", node="stt.vad", probability=prob)

            self._speech_buffer.append(pcm_frame)
            self._silence_frame_count = 0
        else:
            if self._is_speaking:
                self._silence_frame_count += 1
                self._speech_buffer.append(pcm_frame)

                if self._silence_frame_count >= SILENCE_FRAMES_TO_END:
                    # End of speech segment
                    is_speech_end = True
                    self._is_speaking = False
                    accumulated_audio = b"".join(self._speech_buffer)
                    self._speech_buffer = []
                    self._silence_frame_count = 0

                    logger.debug(
                        "Speech end detected",
                        node="stt.vad",
                        audio_duration_ms=len(accumulated_audio) // (SAMPLE_RATE * 2 // 1000),
                    )

                    if on_speech_end:
                        on_speech_end(accumulated_audio)

        return {
            "is_speech": is_speech,
            "probability": prob,
            "is_speech_end": is_speech_end,
        }

    def reset(self) -> None:
        """Reset VAD state (call between sessions)."""
        self._is_speaking = False
        self._silence_frame_count = 0
        self._speech_buffer = []
