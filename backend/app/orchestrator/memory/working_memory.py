from __future__ import annotations

from typing import Any


def get_working_memory(state: dict[str, Any]) -> dict[str, Any]:
    """Extract working memory fields from AgentState as a plain dict."""
    wm = state.get("working_memory")
    if wm and hasattr(wm, "model_dump"):
        return wm.model_dump()
    return {}


def update_last_tool_result(state: dict[str, Any], tool_name: str, result: Any) -> None:
    """Update working_memory.last_tool_result with the latest tool call result."""
    wm = state.get("working_memory")
    if wm:
        wm.last_tool_result = {"tool": tool_name, "result": result if isinstance(result, dict) else str(result)}


def add_diagnostic(state: dict[str, Any], diagnostic_id: str) -> None:
    """Record a completed diagnostic in working_memory.diagnostics_run."""
    wm = state.get("working_memory")
    if wm and diagnostic_id not in wm.diagnostics_run:
        wm.diagnostics_run.append(diagnostic_id)


def set_pending_action(state: dict[str, Any], action: str | None) -> None:
    """Set or clear the pending action in working memory."""
    wm = state.get("working_memory")
    if wm:
        wm.pending_action = action
