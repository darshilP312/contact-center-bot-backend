from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.conversation import ConversationState, CustomerInfo
from app.models.flags import SessionFlags
from app.models.intent import IntentInfo
from app.models.memory import LongTermMemory, WorkingMemory
from app.models.metrics import ObservabilityMetrics
from app.models.workflow import WorkflowState

logger = get_logger("session.manager")
settings = get_settings()

SESSION_KEY = "session:{session_id}"
SESSION_LOCK_KEY = "session:{session_id}:lock"


def _session_key(session_id: str) -> str:
    return f"session:{session_id}"


def _lock_key(session_id: str) -> str:
    return f"session:{session_id}:lock"


class SessionManager:
    """
    Redis-backed session state CRUD.

    Stores all session sub-models as a JSON blob in a Redis Hash.
    Provides distributed locking via SET NX EX pattern to prevent
    concurrent orchestrator invocations for the same session.
    """

    def __init__(self, redis: aioredis.Redis) -> None:
        self.redis = redis
        self.ttl = settings.REDIS_SESSION_TTL_SECONDS

    async def create_session(
        self,
        domain: str,
        language: str = "en",
        channel: str = "voice",
        session_id: Optional[str] = None,
    ) -> ConversationState:
        """
        Create a new session with default state for all sub-models.

        Args:
            domain: Active domain plugin ID.
            language: ISO 639-1 language code.
            channel: voice | chat | hybrid.
            session_id: Optional pre-specified session ID.

        Returns:
            The created ConversationState.
        """
        sid = session_id or f"sess_{uuid.uuid4().hex[:12]}"

        conversation = ConversationState(
            session_id=sid,
            channel=channel,  # type: ignore[arg-type]
        )

        customer = CustomerInfo(
            session_id=sid,
            verified=True,
            customer_id="CUST-1001",
            name="Priya Patel",
            tier="premium",
            phone="+91-9876543210",
            account_no="ACC-9876-1234",
        )

        state = {
            "session_id": sid,
            "domain": domain,
            "language": language,
            "conversation": conversation.model_dump(mode="json"),
            "customer": customer.model_dump(mode="json"),
            "intent": IntentInfo(session_id=sid).model_dump(mode="json"),
            "workflow": WorkflowState(session_id=sid).model_dump(mode="json"),
            "flags": SessionFlags(session_id=sid).model_dump(mode="json"),
            "working_memory": WorkingMemory(session_id=sid).model_dump(mode="json"),
            "long_term_memory": LongTermMemory(session_id=sid).model_dump(mode="json"),
            "metrics": ObservabilityMetrics(session_id=sid).model_dump(mode="json"),
            "created_at": datetime.utcnow().isoformat(),
        }

        key = _session_key(sid)
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.hset(key, "data", json.dumps(state))
            pipe.expire(key, self.ttl)
            await pipe.execute()

        logger.info("Session created", session_id=sid, node="session.manager", domain=domain)
        return conversation

    async def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        """
        Retrieve session state as a raw dictionary.

        Returns:
            Session state dict, or None if session does not exist.
        """
        key = _session_key(session_id)
        raw = await self.redis.hget(key, "data")

        if raw is None:
            return None

        # Refresh TTL on access
        await self.redis.expire(key, self.ttl)
        return json.loads(raw)

    async def update_session(self, session_id: str, state: dict[str, Any]) -> None:
        """
        Overwrite full session state.

        Args:
            session_id: Session ID.
            state: Complete session state dict.
        """
        key = _session_key(session_id)
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.hset(key, "data", json.dumps(state))
            pipe.expire(key, self.ttl)
            await pipe.execute()

    async def update_session_from_state(
        self, session_id: str, agent_state: dict[str, Any]
    ) -> None:
        """
        Update session from a LangGraph AgentState dict.

        Serialises all Pydantic models in the state to JSON-compatible dicts.
        """
        existing = await self.get_session(session_id) or {}

        def _serialize(val: Any) -> Any:
            if hasattr(val, "model_dump"):
                return val.model_dump(mode="json")
            return val

        updated = {
            **existing,
            "conversation": _serialize(agent_state.get("conversation")),
            "customer": _serialize(agent_state.get("customer")),
            "intent": _serialize(agent_state.get("intent")),
            "workflow": _serialize(agent_state.get("workflow")),
            "flags": _serialize(agent_state.get("flags")),
            "working_memory": _serialize(agent_state.get("working_memory")),
            "long_term_memory": _serialize(agent_state.get("long_term_memory")),
            "metrics": _serialize(agent_state.get("metrics")),
        }

        await self.update_session(session_id, updated)

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a session from Redis.

        Returns:
            True if session existed and was deleted, False if not found.
        """
        key = _session_key(session_id)
        deleted = await self.redis.delete(key)
        # Also remove lock if exists
        await self.redis.delete(_lock_key(session_id))
        return deleted > 0

    async def acquire_lock(self, session_id: str, timeout_seconds: int = 30) -> bool:
        """
        Acquire distributed lock for a session (prevents concurrent orchestrator invocations).

        Uses SET NX EX pattern — atomic lock acquisition.

        Args:
            session_id: Session to lock.
            timeout_seconds: Lock TTL in seconds.

        Returns:
            True if lock acquired, False if already locked.
        """
        lock_key = _lock_key(session_id)
        result = await self.redis.set(lock_key, "1", nx=True, ex=timeout_seconds)
        return result is not None

    async def release_lock(self, session_id: str) -> None:
        """Release the distributed lock for a session."""
        await self.redis.delete(_lock_key(session_id))
