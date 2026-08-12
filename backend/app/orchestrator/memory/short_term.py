from __future__ import annotations

import json
from typing import Any, List

import redis.asyncio as aioredis

from app.models.transcript import TranscriptEntry

STM_KEY = "stm:{session_id}"
DEFAULT_HISTORY_SIZE = 10


class ShortTermMemory:
    """
    Redis-backed short-term memory storing the last N conversation turns.

    Uses a Redis list with LPUSH/LTRIM to maintain a bounded conversation history.
    Each entry is a serialised TranscriptEntry JSON.
    """

    def __init__(self, redis: aioredis.Redis) -> None:
        self.redis = redis

    def _key(self, session_id: str) -> str:
        return f"stm:{session_id}"

    async def append_entry(self, session_id: str, entry: TranscriptEntry) -> None:
        """
        Append a transcript entry to the STM.

        Maintains a bounded list of the last 50 entries.
        """
        key = self._key(session_id)
        await self.redis.lpush(key, entry.model_dump_json())
        await self.redis.ltrim(key, 0, 49)  # Keep last 50 entries
        await self.redis.expire(key, 3600)

    async def get_history(
        self, session_id: str, n: int = DEFAULT_HISTORY_SIZE
    ) -> List[TranscriptEntry]:
        """
        Get the last N transcript entries in chronological order.

        Args:
            session_id: Session ID.
            n: Number of entries to retrieve.

        Returns:
            List of TranscriptEntry objects, oldest first.
        """
        key = self._key(session_id)
        raw_entries = await self.redis.lrange(key, 0, n - 1)

        entries = []
        for raw in reversed(raw_entries):  # Reverse: Redis list is newest-first
            try:
                data = json.loads(raw)
                entries.append(TranscriptEntry(**data))
            except (json.JSONDecodeError, ValueError):
                continue

        return entries

    async def clear(self, session_id: str) -> None:
        """Clear all STM entries for a session."""
        await self.redis.delete(self._key(session_id))

    async def get_formatted_history(
        self, session_id: str, n: int = DEFAULT_HISTORY_SIZE
    ) -> str:
        """
        Get conversation history formatted for LLM context.

        Returns a human-readable transcript block suitable for inclusion
        in a system or user prompt.
        """
        entries = await self.get_history(session_id, n)
        if not entries:
            return "(No conversation history yet)"

        lines = []
        for entry in entries:
            role_label = {
                "customer": "Customer",
                "agent": "Agent",
                "system": "System",
            }.get(entry.role, "Unknown")
            lines.append(f"{role_label}: {entry.text}")

        return "\n".join(lines)
