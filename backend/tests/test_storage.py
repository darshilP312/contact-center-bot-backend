"""
test_storage.py — Tests for session storage layer (Redis and In-Memory fallback).
"""

import pytest
from app.state import ConversationState
from app.storage import InMemorySessionStorage


@pytest.mark.asyncio
async def test_in_memory_storage_get_save():
    storage = InMemorySessionStorage()

    state = ConversationState(session_id="test_sess_001")
    state.customer.name = "Test User"
    state.intent.name = "technical_support"

    await storage.save_session(state)

    loaded = await storage.get_session("test_sess_001")
    assert loaded is not None
    assert loaded.session_id == "test_sess_001"
    assert loaded.customer.name == "Test User"
    assert loaded.intent.name == "technical_support"


@pytest.mark.asyncio
async def test_in_memory_storage_non_existent():
    storage = InMemorySessionStorage()
    loaded = await storage.get_session("non_existent_session")
    assert loaded is None
