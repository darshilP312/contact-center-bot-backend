from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger("orchestrator.workflow_executor")


async def workflow_executor_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    Workflow Executor Node — maps to diagram node P (Business Processes).

    Responsibilities:
    1. Mark the current workflow step as completed
    2. Record tool results for this step in WorkflowState.step_results
    3. Advance to the next workflow step
    4. Emit workflow.update WebSocket event

    Input:  state.workflow, state.tool_results, state._domain_loader
    Output: state.workflow updated (completed_steps, step, step_results)
    """
    session_id = state.get("session_id", "none")
    ws = state.get("_ws_connection")
    domain_loader = state.get("_domain_loader")
    domain = state.get("domain", "insurance")
    workflow = state.get("workflow")
    tool_results = state.get("tool_results", [])

    if not workflow or not workflow.name or not workflow.step:
        return state

    current_step_id = workflow.step

    # Mark current step completed
    if current_step_id not in workflow.completed_steps:
        workflow.completed_steps.append(current_step_id)

    # Record tool results for this step
    successful_results = {tr["tool"]: tr["result"] for tr in tool_results if tr.get("status") == "success"}
    workflow.step_results[current_step_id] = successful_results

    # Find next step from workflow config
    workflow_config = None
    if domain_loader:
        workflow_config = domain_loader.get_workflow(domain, workflow.name)

    next_step = None
    total_steps = 0
    if workflow_config:
        steps = workflow_config.get("steps", [])
        total_steps = len(steps)
        completed_set = set(workflow.completed_steps)

        # Find first uncompleted step
        intent = state.get("intent")
        entities = intent.entities if intent else {}
        has_policy_no = bool(entities.get("policy_number"))

        for step in steps:
            if step["id"] not in completed_set:
                if step["id"] == "lookup_specific_policy" and not has_policy_no:
                    workflow.completed_steps.append(step["id"])
                    continue
                next_step = step["id"]
                break

    workflow.step = next_step  # None if workflow is complete

    logger.info(
        "Workflow step advanced",
        session_id=session_id,
        node="workflow_executor",
        workflow=workflow.name,
        completed_step=current_step_id,
        next_step=next_step,
        completed_count=len(workflow.completed_steps),
        total_steps=total_steps,
    )

    # Emit WebSocket event
    if ws:
        workflow_name = (workflow_config or {}).get("workflow_name", workflow.name) if workflow_config else workflow.name
        await ws.send_json(
            "workflow.update",
            {
                "workflow_name": workflow_name,
                "current_step": next_step,
                "completed_steps": workflow.completed_steps,
                "total_steps": total_steps,
                "session_id": session_id,
                "step_complete": True,
            },
        )

    return state
