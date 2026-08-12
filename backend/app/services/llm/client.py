from __future__ import annotations

import json
import time
from typing import Any, AsyncGenerator

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("llm.client")


class LLMClient:
    """
    OpenAI-compatible LLM client.

    Supports any endpoint that implements the OpenAI Chat Completions API:
    - Groq: api.groq.com/openai/v1
    - Google Gemini: generativelanguage.googleapis.com/v1beta/openai/
    - Azure OpenAI: {resource}.openai.azure.com/openai/deployments/{deployment}
    - Local Ollama: localhost:11434/v1

    All LLM calls are async and non-blocking.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=2,
        )
        self.model = settings.LLM_MODEL
        self.temperature = settings.LLM_TEMPERATURE
        self.max_tokens = settings.LLM_MAX_TOKENS

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        session_id: str = "none",
        node: str = "llm",
    ) -> str:
        """
        Single-turn chat completion.

        Args:
            messages: List of {"role": ..., "content": ...} dicts.
            temperature: Override default temperature.
            max_tokens: Override default max tokens.
            session_id: For logging context.
            node: LangGraph node name for logging.

        Returns:
            Response text string.
        """
        start = time.monotonic()

        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature or self.temperature,
            max_tokens=max_tokens or self.max_tokens,
        )

        latency_ms = int((time.monotonic() - start) * 1000)
        content = response.choices[0].message.content or ""

        logger.info(
            "LLM completion",
            session_id=session_id,
            node=node,
            latency_ms=latency_ms,
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
        )

        return content

    async def structured_completion(
        self,
        messages: list[dict[str, str]],
        json_schema: dict[str, Any],
        temperature: float | None = None,
        session_id: str = "none",
        node: str = "llm",
    ) -> dict[str, Any]:
        """
        Structured output completion returning parsed JSON.

        Attempts to use response_format=json_schema for providers that support it
        (OpenAI, compatible providers). Falls back to prompt-based JSON extraction
        for providers that don't support structured output.

        Args:
            messages: Chat messages.
            json_schema: JSON Schema dict defining the expected output structure.
            temperature: Override temperature (default 0.0 for structured output).
            session_id: For logging context.
            node: LangGraph node name.

        Returns:
            Parsed JSON dict matching the provided schema.
        """
        start = time.monotonic()
        temp = temperature if temperature is not None else 0.0

        try:
            # Attempt structured output
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temp,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"

        except Exception:
            # Fallback: add JSON instruction to prompt
            augmented_messages = messages.copy()
            schema_str = json.dumps(json_schema, indent=2)
            augmented_messages[-1]["content"] += (
                f"\n\nIMPORTANT: Respond ONLY with valid JSON matching this schema:\n{schema_str}"
            )

            response = await self._client.chat.completions.create(
                model=self.model,
                messages=augmented_messages,
                temperature=temp,
                max_tokens=self.max_tokens,
            )
            content = response.choices[0].message.content or "{}"

        latency_ms = int((time.monotonic() - start) * 1000)

        logger.info(
            "LLM structured completion",
            session_id=session_id,
            node=node,
            latency_ms=latency_ms,
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
        )

        # Parse JSON, extracting from code blocks if needed
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.error(
                "Failed to parse LLM JSON response",
                session_id=session_id,
                node=node,
                raw_response=content[:200],
            )
            return {}

    async def stream_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        session_id: str = "none",
        node: str = "llm",
    ) -> AsyncGenerator[str, None]:
        """
        Streaming completion — yields text tokens as they arrive.

        Args:
            messages: Chat messages.
            temperature: Override temperature.
            session_id: For logging context.
            node: LangGraph node name.

        Yields:
            Text token strings.
        """
        stream = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature or self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
        )

        total_tokens = 0
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                total_tokens += 1
                yield delta.content

        logger.info(
            "LLM stream completion",
            session_id=session_id,
            node=node,
            approx_completion_tokens=total_tokens,
        )
