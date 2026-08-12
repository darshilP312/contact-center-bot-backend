from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger("orchestrator.business_router")


async def business_router_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    Business Router Node — maps to diagram node K (Business Context Router).

    Responsibilities:
    1. Map the detected intent to the appropriate domain workflow
    2. Load the workflow YAML configuration
    3. Update WorkflowState with workflow name and first pending step
    4. Emit workflow.update WebSocket event

    Input:  state.intent, state.domain
    Output: state.workflow (name, step set), WebSocket workflow.update event
    """
    session_id = state.get("session_id", "none")
    ws = state.get("_ws_connection")
    domain_loader = state.get("_domain_loader")
    domain = state.get("domain", "insurance")
    intent = state.get("intent")
    workflow = state.get("workflow")

    if not intent or not intent.name:
        return state

    # Get intent → workflow mapping from domain YAML
    intent_config = {}
    if domain_loader:
        intent_config = domain_loader.get_intent(domain, intent.name) or {}

    workflow_id = intent_config.get("maps_to_workflow")

    if not workflow_id:
        # No workflow for this intent (RAG-only or single-tool intents)
        logger.debug(
            "No workflow for intent — skipping routing",
            session_id=session_id,
            node="business_router",
            intent=intent.name,
        )
        return state

    # Load workflow config
    workflow_config = None
    if domain_loader:
        workflow_config = domain_loader.get_workflow(domain, workflow_id)

    if not workflow_config:
        logger.warning(
            "Workflow config not found",
            session_id=session_id,
            node="business_router",
            workflow_id=workflow_id,
        )
        return state

    # Update WorkflowState
    if workflow:
        steps = workflow_config.get("steps", [])
        completed = set(workflow.completed_steps)

        if workflow.name != workflow_id:
            # New workflow — start from the beginning
            workflow.name = workflow_id
            workflow.completed_steps = []
            if steps:
                workflow.step = steps[0]["id"]
        else:
            # Continuing existing workflow — find next uncompleted step
            for step in steps:
                if step["id"] not in completed:
                    workflow.step = step["id"]
                    break

        total_steps = len(steps)
        completed_steps = list(workflow.completed_steps)

        logger.info(
            "Workflow routed",
            session_id=session_id,
            node="business_router",
            workflow_id=workflow_id,
            current_step=workflow.step,
            completed_steps=completed_steps,
        )

        # Emit WebSocket event
        if ws:
            await ws.send_json(
                "workflow.update",
                {
                    "workflow_name": workflow_config.get("workflow_name", workflow_id),
                    "current_step": workflow.step,
                    "completed_steps": completed_steps,
                    "total_steps": total_steps,
                    "session_id": session_id,
                },
            )

    return state
