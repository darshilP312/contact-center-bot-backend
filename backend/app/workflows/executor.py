"""
executor.py — Workflow step tracker and transition resolver.
Reads the YAML-defined transition rules and updates ConversationState accordingly.
The orchestrator walks the graph; business flow is never hard-coded here.
"""

from __future__ import annotations

from typing import Any

from app.workflows.loader import load_workflow, StepDefinition


def advance_workflow(state: dict, tool_result: dict) -> dict:
    """
    Given the completed tool result, determine the next workflow step
    and update the ConversationState dict in place.

    Args:
        state:       ConversationState as a plain dict.
        tool_result: ToolResult dict returned by the executed tool.

    Returns:
        Updated state dict.
    """
    workflow_name = state.get("workflow", {}).get("name")
    current_step_id = state.get("workflow", {}).get("step")

    if not workflow_name or not current_step_id:
        return state

    try:
        wf = load_workflow(workflow_name)
    except FileNotFoundError:
        return state

    step_def = wf.get_step(current_step_id)
    if not step_def:
        return state

    # Mark current step completed
    completed = state["workflow"].get("completed_steps", [])
    if current_step_id not in completed:
        completed.append(current_step_id)
    state["workflow"]["completed_steps"] = completed
    state["workflow"]["step_results"][current_step_id] = tool_result.get("data", {})

    # Resolve next step
    next_step = _resolve_next_step(step_def, tool_result, state)

    if next_step:
        state["workflow"]["step"] = next_step
    elif step_def.terminal:
        state["workflow"]["step"] = None  # conversation complete

    # Update flags based on tool result data
    _apply_result_flags(state, tool_result.get("data", {}))

    return state


def _resolve_next_step(
    step: StepDefinition,
    tool_result: dict,
    state: dict,
) -> str | None:
    """
    Determine the next step based on the tool result and step transition rules.

    Resolution order:
    1. Branch conditions (check result data for specific keys)
    2. on_success / on_fail based on ok flag
    3. on_exhausted if max_attempts reached
    4. Terminal → None
    """
    ok = tool_result.get("ok", False)
    data = tool_result.get("data", {})

    # Branch conditions — check for specific keys in tool result data
    for branch_condition, branch_target in step.branch.items():
        if data.get(branch_condition) is True:
            return branch_target

    # Exhaustion check
    current_step_id = state.get("workflow", {}).get("step")
    attempts = state.get("workflow", {}).get("step_attempts", {}).get(current_step_id, 0)
    if not ok and step.on_exhausted and attempts >= step.max_attempts:
        return step.on_exhausted

    # Standard success/fail
    if ok:
        return step.on_success
    else:
        return step.on_fail


def _apply_result_flags(state: dict, data: dict) -> None:
    """Update SessionFlags based on tool result data."""
    flags = state.get("flags", {})

    if data.get("ticket_created") or data.get("ticket_id"):
        flags["ticket_created"] = True
        if data.get("ticket_id"):
            state["ticket_id"] = data["ticket_id"]

    if data.get("engineer_booked"):
        flags["engineer_booked"] = True

    if data.get("refund_triggered"):
        flags["refund_triggered"] = True

    state["flags"] = flags


def get_step_goal(workflow_name: str, step_id: str) -> str:
    """Utility: get the goal text for a specific workflow step."""
    try:
        wf = load_workflow(workflow_name)
        step = wf.get_step(step_id)
        return step.goal if step else "Complete the current step."
    except Exception:
        return "Complete the current step."
