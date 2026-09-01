"""
Redis Async Cache Layer

Multi-layer caching for RAG query results with connection pooling,
TTL-based expiration, and graceful degradation when Redis is unavailable.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

from .config import RAGConfig, rag_config

logger = logging.getLogger("rag.cache")


class RAGCache:
    """
    Async Redis cache for RAG search results.

    - Connection pooling (configurable, default 50 connections) for concurrency
    - TTL-based cache expiration (default 5 minutes)
    - Graceful degradation: if Redis is unavailable, returns None (no crash)
    - Key format: rag:v1:{domain}:{query_hash}
    """

    KEY_PREFIX = "rag:v1"

    def __init__(self, config: Optional[RAGConfig] = None) -> None:
        self.config = config or rag_config
        self._pool = None
        self._available = False

    async def initialize(self) -> bool:
        """
        Connect to Redis with connection pooling.
        Returns True if connected, False if unavailable (graceful degradation).
        """
        if not self.config.enable_redis:
            logger.info("Redis caching disabled by configuration")
            return False

        try:
            import redis.asyncio as aioredis

            self._pool = aioredis.ConnectionPool(
                host=self.config.redis_host,
                port=self.config.redis_port,
                db=self.config.redis_db,
                password=self.config.redis_password or None,
                max_connections=self.config.redis_max_connections,
                decode_responses=True,
            )

            # Verify connection
            client = aioredis.Redis(connection_pool=self._pool)
            await client.ping()
            await client.aclose()

            self._available = True
            logger.info(
                f"Redis cache connected: {self.config.redis_host}:{self.config.redis_port} "
                f"(pool_size={self.config.redis_max_connections})"
            )
            return True

        except ImportError:
            logger.warning("redis package not installed — caching disabled")
            self._available = False
            return False
        except Exception as e:
            logger.warning(
                f"Redis not available ({e}) — RAG will operate without caching. "
                f"Install and start Redis for improved performance."
            )
            self._available = False
            return False

    def _make_key(self, query: str, domain: Optional[str] = None) -> str:
        """Generate a deterministic cache key from query and domain."""
        raw = f"{domain or 'all'}:{query.strip().lower()}"
        query_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        return f"{self.KEY_PREFIX}:{domain or 'all'}:{query_hash}"

    async def get(
        self, query: str, domain: Optional[str] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Check cache for query results.

        Returns:
            Cached results if found, None on miss or if Redis is unavailable.
        """
        if not self._available or not self._pool:
            return None

        try:
            import redis.asyncio as aioredis

            client = aioredis.Redis(connection_pool=self._pool)
            key = self._make_key(query, domain)
            cached = await client.get(key)
            await client.aclose()

            if cached:
                logger.debug(f"Cache HIT: {key}")
                return json.loads(cached)
            else:
                logger.debug(f"Cache MISS: {key}")
                return None

        except Exception as e:
            logger.warning(f"Redis get error: {e}")
            return None

    async def set(
        self,
        query: str,
        results: List[Dict[str, Any]],
        domain: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Cache query results with TTL.

        Returns:
            True if cached successfully, False on error.
        """
        if not self._available or not self._pool:
            return False

        try:
            import redis.asyncio as aioredis

            client = aioredis.Redis(connection_pool=self._pool)
            key = self._make_key(query, domain)
            cache_ttl = ttl or self.config.cache_ttl

            await client.setex(key, cache_ttl, json.dumps(results))
            await client.aclose()

            logger.debug(f"Cache SET: {key} (TTL={cache_ttl}s)")
            return True

        except Exception as e:
            logger.warning(f"Redis set error: {e}")
            return False

    async def invalidate(self, domain: Optional[str] = None) -> int:
        """
        Invalidate (flush) cached results for a domain or all.

        Returns:
            Number of keys deleted.
        """
        if not self._available or not self._pool:
            return 0

        try:
            import redis.asyncio as aioredis

            client = aioredis.Redis(connection_pool=self._pool)
            pattern = f"{self.KEY_PREFIX}:{domain or '*'}:*"
            keys = []
            async for key in client.scan_iter(match=pattern, count=100):
                keys.append(key)

            deleted = 0
            if keys:
                deleted = await client.delete(*keys)

            await client.aclose()
            logger.info(f"Cache invalidated: {deleted} keys (pattern={pattern})")
            return deleted

        except Exception as e:
            logger.warning(f"Redis invalidate error: {e}")
            return 0

    async def close(self) -> None:
        """Close Redis connection pool."""
        if self._pool:
            try:
                await self._pool.disconnect()
                logger.info("Redis connection pool closed")
            except Exception as e:
                logger.warning(f"Error closing Redis pool: {e}")
            finally:
                self._pool = None
                self._available = False

    async def ping(self) -> bool:
        """Health check — verify Redis is responsive."""
        if not self._available or not self._pool:
            return False

        try:
            import redis.asyncio as aioredis

            client = aioredis.Redis(connection_pool=self._pool)
            result = await client.ping()
            await client.aclose()
            return bool(result)
        except Exception:
            return False

    @property
    def is_available(self) -> bool:
        return self._available
