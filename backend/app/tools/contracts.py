"""
contracts.py — ToolResult: the uniform return type for every enterprise tool.
Every tool MUST return this shape. Never raise unhandled exceptions.
"""

from typing import Any, Optional
from typing_extensions import TypedDict


class ToolResult(TypedDict):
    """Standard return type for all enterprise tool functions."""
    ok: bool
    data: dict[str, Any]    # populated when ok=True
    error: Optional[str]    # populated when ok=False


class ToolDefinition(TypedDict):
    """Schema shown to the LLM for tool selection (planning node)."""
    name: str
    description: str
    input_schema: dict[str, Any]


def ok_result(data: dict) -> ToolResult:
    """Convenience constructor for a successful tool result."""
    return {"ok": True, "data": data, "error": None}


def err_result(error: str) -> ToolResult:
    """Convenience constructor for a failed tool result."""
    return {"ok": False, "data": {}, "error": error}
