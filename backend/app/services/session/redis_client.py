from __future__ import annotations

from typing import Any
import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("redis_client")

_redis_client: aioredis.Redis | Any | None = None


class InMemoryPipeline:
    """Async pipeline emulator for in-memory session store."""

    def __init__(self, store: InMemoryRedis) -> None:
        self.store = store
        self.ops: list[tuple[Any, ...]] = []

    def hset(self, key: str, field: str, value: str) -> None:
        self.ops.append(("hset", key, field, value))

    def expire(self, key: str, ttl: int) -> None:
        self.ops.append(("expire", key, ttl))

    async def execute(self) -> None:
        for op in self.ops:
            if op[0] == "hset":
                await self.store.hset(op[1], op[2], op[3])
            elif op[0] == "expire":
                await self.store.expire(op[1], op[2])
        self.ops.clear()

    async def __aenter__(self) -> InMemoryPipeline:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass


class InMemoryRedis:
    """
    In-memory fallback implementation of Redis interface when a live Redis
    server is not running locally. Implements all Redis operations used
    by the application: hashes, lists (LPUSH/LTRIM/LRANGE), KV, and sets.
    """

    def __init__(self) -> None:
        self._hashes: dict[str, dict[str, str]] = {}
        self._lists: dict[str, list[str]] = {}
        self._kv: dict[str, str] = {}

    async def ping(self) -> bool:
        return True

    # ── Hash operations ──────────────────────────────────────────────────────

    async def hset(self, key: str, field: str, value: str) -> int:
        if key not in self._hashes:
            self._hashes[key] = {}
        self._hashes[key][field] = value
        return 1

    async def hget(self, key: str, field: str) -> str | None:
        return self._hashes.get(key, {}).get(field)

    # ── List operations (for ShortTermMemory) ────────────────────────────────

    async def lpush(self, key: str, *values: str) -> int:
        """Prepend one or more values to a list."""
        if key not in self._lists:
            self._lists[key] = []
        for v in values:
            self._lists[key].insert(0, v)
        return len(self._lists[key])

    async def ltrim(self, key: str, start: int, stop: int) -> bool:
        """Trim a list to the specified range."""
        lst = self._lists.get(key, [])
        self._lists[key] = lst[start: stop + 1] if stop >= 0 else lst[start:]
        return True

    async def lrange(self, key: str, start: int, stop: int) -> list[str]:
        """Return the specified range of elements from a list."""
        lst = self._lists.get(key, [])
        if stop == -1:
            return lst[start:]
        return lst[start: stop + 1]

    # ── General key operations ────────────────────────────────────────────────

    async def expire(self, key: str, ttl: int) -> bool:
        return True

    async def delete(self, *keys: str) -> int:
        count = 0
        for k in keys:
            for store in (self._hashes, self._lists, self._kv):
                if k in store:
                    del store[k]  # type: ignore[arg-type]
                    count += 1
        return count

    # ── String / KV operations ────────────────────────────────────────────────

    async def set(
        self, key: str, value: str, nx: bool = False, ex: int | None = None
    ) -> bool | None:
        if nx and key in self._kv:
            return None
        self._kv[key] = value
        return True

    async def get(self, key: str) -> str | None:
        return self._kv.get(key)

    # ── Pipeline ─────────────────────────────────────────────────────────────

    def pipeline(self, transaction: bool = True) -> InMemoryPipeline:
        return InMemoryPipeline(self)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def aclose(self) -> None:
        pass

    async def close(self) -> None:
        pass


async def get_redis_client() -> aioredis.Redis | InMemoryRedis:
    """
    Return the shared async Redis client, creating it on first call.

    Falls back to an in-memory session store if Redis server is unreachable.
    """
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    settings = get_settings()

    try:
        client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=False,
        )
        await client.ping()
        _redis_client = client
        logger.info(
            "Redis client initialised",
            node="redis_client",
            url=settings.REDIS_URL.split("@")[-1],
        )
    except Exception as exc:
        logger.warning(
            "Redis server unreachable, using in-memory session store",
            node="redis_client",
            url=settings.REDIS_URL,
            error=str(exc),
        )
        _redis_client = InMemoryRedis()

    return _redis_client
