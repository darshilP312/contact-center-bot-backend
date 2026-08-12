"""Unit tests for session manager."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.session.manager import SessionManager


class TestSessionManager:
    @pytest.fixture
    def manager(self, mock_redis):
        return SessionManager(mock_redis)

    @pytest.mark.asyncio
    async def test_create_session_returns_conversation(self, manager):
        result = await manager.create_session(domain="insurance", language="en")
        assert result.session_id.startswith("sess_")
        assert result.channel == "voice"

    @pytest.mark.asyncio
    async def test_create_session_with_custom_id(self, manager):
        result = await manager.create_session(
            domain="insurance", session_id="sess_custom123"
        )
        assert result.session_id == "sess_custom123"

    @pytest.mark.asyncio
    async def test_get_session_returns_none_when_not_found(self, manager, mock_redis):
        mock_redis.hget = AsyncMock(return_value=None)
        result = await manager.get_session("sess_missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_session_returns_data_when_found(self, manager, mock_redis):
        session_data = {
            "session_id": "sess_123",
            "domain": "insurance",
            "conversation": {"session_id": "sess_123", "turn_count": 2},
        }
        mock_redis.hget = AsyncMock(return_value=json.dumps(session_data))
        result = await manager.get_session("sess_123")
        assert result is not None
        assert result["domain"] == "insurance"

    @pytest.mark.asyncio
    async def test_delete_session_returns_true_when_deleted(self, manager, mock_redis):
        mock_redis.delete = AsyncMock(return_value=1)
        result = await manager.delete_session("sess_123")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_session_returns_false_when_not_found(self, manager, mock_redis):
        mock_redis.delete = AsyncMock(return_value=0)
        result = await manager.delete_session("sess_missing")
        assert result is False

    @pytest.mark.asyncio
    async def test_acquire_lock_returns_true_on_success(self, manager, mock_redis):
        mock_redis.set = AsyncMock(return_value=True)
        result = await manager.acquire_lock("sess_123")
        assert result is True

    @pytest.mark.asyncio
    async def test_acquire_lock_returns_false_when_already_locked(self, manager, mock_redis):
        mock_redis.set = AsyncMock(return_value=None)
        result = await manager.acquire_lock("sess_123")
        assert result is False
