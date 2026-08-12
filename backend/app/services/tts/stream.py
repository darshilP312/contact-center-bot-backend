from __future__ import annotations

import re
from typing import AsyncGenerator, Callable

from app.core.logging import get_logger

logger = get_logger("tts.stream")

# Sentence boundary pattern — handles English and Indic sentence endings
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?।\u0964])\s+")
MIN_SENTENCE_LENGTH = 20  # Don't synthesise fragments shorter than this


class TTSStreamCoordinator:
    """
    Sentence-boundary streaming TTS coordinator.

    Receives LLM token stream, detects sentence boundaries, and synthesises
    each sentence independently — allowing audio playback to begin before the
    full response is generated.

    Supports: English (. ! ?) and Indic (। \u0964 Devanagari danda)
    """

    def __init__(self, tts, ws_send_binary: Callable[[bytes], None]) -> None:
        """
        Args:
            tts: TTS provider instance (KokoroTTS or EdgeTTSFallback).
            ws_send_binary: Async callable to send audio bytes to WebSocket.
        """
        self.tts = tts
        self.ws_send_binary = ws_send_binary
        self._buffer = ""
        self._sentences_synthesised = 0

    def _split_sentences(self, text: str) -> tuple[list[str], str]:
        """
        Split text on sentence boundaries.

        Returns:
            (complete_sentences, remaining_buffer)
        """
        parts = SENTENCE_BOUNDARY.split(text)
        if len(parts) <= 1:
            return [], text

        # Last part is incomplete (no trailing boundary)
        complete = parts[:-1]
        remaining = parts[-1]
        return complete, remaining

    async def stream_text(
        self,
        token_generator: AsyncGenerator[str, None],
        voice: str | None = None,
    ) -> str:
        """
        Process an LLM token stream, synthesise sentence by sentence.

        Args:
            token_generator: Async generator of LLM text tokens.
            voice: Voice ID override.

        Returns:
            Complete response text (all tokens concatenated).
        """
        full_text = ""

        async for token in token_generator:
            self._buffer += token
            full_text += token

            # Check for sentence boundaries in buffer
            sentences, self._buffer = self._split_sentences(self._buffer)

            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) >= MIN_SENTENCE_LENGTH:
                    await self._synthesize_and_stream(sentence, voice)

        # Synthesise any remaining buffered text
        remaining = self._buffer.strip()
        if len(remaining) >= 5:
            await self._synthesize_and_stream(remaining, voice)

        self._buffer = ""
        return full_text

    async def synthesize_full(self, text: str, voice: str | None = None) -> None:
        """
        Synthesise a complete text string (non-streaming, for short responses).

        Splits into sentences and synthesises each one, then streams audio.
        """
        sentences = SENTENCE_BOUNDARY.split(text.strip())
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence:
                await self._synthesize_and_stream(sentence, voice)

    async def _synthesize_and_stream(self, sentence: str, voice: str | None) -> None:
        """Synthesise one sentence and stream audio chunks to WebSocket."""
        try:
            self._sentences_synthesised += 1
            logger.debug(
                "Synthesising sentence",
                node="tts.stream",
                sentence_number=self._sentences_synthesised,
                text=sentence[:50],
            )

            async for audio_chunk in self.tts.synthesize(sentence, voice=voice):
                await self.ws_send_binary(audio_chunk)

        except Exception as e:
            logger.error(
                "TTS synthesis failed for sentence",
                node="tts.stream",
                error=str(e),
                sentence=sentence[:50],
            )
            # Continue with next sentence — don't fail entire response
