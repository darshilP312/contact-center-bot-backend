"""
storage.py — Session state persistence layer.
Supports both Redis (production) and In-Memory storage (standalone/AVD mode).
Automatically falls back to In-Memory mode if Redis is not available, allowing
the application to run cleanly on Azure Virtual Desktop without Docker!
"""

from __future__ import annotations

import logging
import asyncio
from typing import Optional
import redis.asyncio as aioredis

from app.config import settings
from app.state import ConversationState

logger = logging.getLogger("cc.storage")


class BaseSessionStorage:
    """Abstract interface for session storage."""

    async def get_session(self, session_id: str) -> Optional[ConversationState]:
        raise NotImplementedError

    async def save_session(self, state: ConversationState, ttl_seconds: int = 3600) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        pass


class InMemorySessionStorage(BaseSessionStorage):
    """
    In-Memory session store for standalone / non-Docker environments.
    Holds session state in a Python dict with TTL support.
    """

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        logger.info("Initialized InMemorySessionStorage (Standalone/Non-Docker mode active).")

    async def get_session(self, session_id: str) -> Optional[ConversationState]:
        raw = self._store.get(f"session:{session_id}")
        if not raw:
            return None
        try:
            return ConversationState.from_redis(raw)
        except Exception as e:
            logger.error(f"Error deserializing in-memory session {session_id}: {e}")
            return None

    async def save_session(self, state: ConversationState, ttl_seconds: int = 3600) -> None:
        self._store[f"session:{state.session_id}"] = state.to_redis()

    async def close(self) -> None:
        self._store.clear()


class RedisSessionStorage(BaseSessionStorage):
    """Redis-backed session storage."""

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client

    async def get_session(self, session_id: str) -> Optional[ConversationState]:
        try:
            raw = await self.redis.get(f"session:{session_id}")
            if not raw:
                return None
            return ConversationState.from_redis(raw)
        except Exception as e:
            logger.error(f"Redis get_session error for {session_id}: {e}")
            return None

    async def save_session(self, state: ConversationState, ttl_seconds: int = 3600) -> None:
        try:
            await self.redis.setex(
                f"session:{state.session_id}",
                ttl_seconds,
                state.to_redis(),
            )
        except Exception as e:
            logger.error(f"Redis save_session error for {state.session_id}: {e}")

    async def close(self) -> None:
        await self.redis.aclose()


# Global storage instance
storage_instance: BaseSessionStorage = InMemorySessionStorage()


async def init_storage() -> BaseSessionStorage:
    """
    Attempts to connect to Redis. If Redis is unavailable or unconfigured,
    gracefully falls back to InMemorySessionStorage.
    """
    global storage_instance

    if not settings.redis_url or "localhost" not in settings.redis_url:
        storage_instance = InMemorySessionStorage()
        return storage_instance

    try:
        r = aioredis.from_url(settings.redis_url, decode_responses=True, socket_timeout=1.5)
        await r.ping()
        logger.info(f"Connected to Redis session store at {settings.redis_url}")
        storage_instance = RedisSessionStorage(r)
    except Exception as e:
        logger.warning(
            f"Could not connect to Redis ({e}). "
            "Falling back to InMemorySessionStorage (Docker-free standalone mode)."
        )
        storage_instance = InMemorySessionStorage()

    return storage_instance


def get_storage() -> BaseSessionStorage:
    """Return active storage instance."""
    return storage_instance
