from __future__ import annotations

import time
from typing import Any

from app.core.logging import get_logger
from app.orchestrator.memory.working_memory import update_last_tool_result

logger = get_logger("orchestrator.tool_caller")


async def tool_caller_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    Tool Caller Node — maps to diagram node O (Tool & API Calls).

    Responsibilities:
    1. For each tool in tools_to_call, look up in domain-scoped ToolRegistry
    2. Execute with typed inputs derived from intent.entities
    3. Store results in tool_results and working_memory.last_tool_result
    4. Increment metrics.tool_calls_made
    5. Retry once on failure, then mark failed and continue
    6. Trace each call via Langfuse span

    Input:  state.tools_to_call, state.intent.entities
    Output: state.tool_results, state.working_memory, state.metrics updated
    """
    session_id = state.get("session_id", "none")
    ws = state.get("_ws_connection")
    tool_registry = state.get("_tool_registry")
    langfuse = state.get("_langfuse")
    domain = state.get("domain", "insurance")
    tools_to_call = state.get("tools_to_call", [])
    intent = state.get("intent")
    entities = intent.entities if intent else {}
    metrics = state.get("metrics")

    if ws:
        await ws.send_json("agent.thinking", {"node": "tool_caller", "status": "running"})

    tool_results = list(state.get("tool_results") or [])

    for tool_name in tools_to_call:
        if not tool_registry:
            logger.warning("No tool registry available", session_id=session_id, node="tool_caller")
            continue

        tool = tool_registry.get_tool(tool_name, domain=domain)
        if not tool:
            logger.warning(
                "Tool not found for domain",
                session_id=session_id,
                node="tool_caller",
                tool_name=tool_name,
                domain=domain,
            )
            tool_results.append({
                "tool": tool_name,
                "status": "not_found",
                "result": {"error": f"Tool '{tool_name}' not available in domain '{domain}'"},
            })
            continue

        start_time = time.monotonic()

        # Build input — try to populate from entities, fall back to session data
        input_data_dict = {**entities}

        # Add commonly needed fields if available in state
        customer = state.get("customer")
        conversation = state.get("conversation")
        workflow = state.get("workflow")

        if customer and customer.customer_id:
            input_data_dict.setdefault("customer_id", customer.customer_id)
        if session_id:
            input_data_dict.setdefault("session_id", session_id)
        if workflow and workflow.name:
            # Extract claim_id if available in recent tool results
            for tr in tool_results:
                if "claim_id" in str(tr.get("result", {})):
                    try:
                        result_dict = tr.get("result", {})
                        if "claim_id" in result_dict:
                            input_data_dict.setdefault("claim_id", result_dict["claim_id"])
                    except Exception:
                        pass

        # Attempt execution with retry
        last_error = None
        for attempt in range(2):
            try:
                # Validate and parse input
                input_obj = tool.input_schema(**{
                    k: v for k, v in input_data_dict.items()
                    if k in tool.input_schema.model_fields
                })

                result_obj = await tool.execute(input_obj)
                latency_ms = int((time.monotonic() - start_time) * 1000)
                result_dict = result_obj.model_dump()

                tool_results.append({
                    "tool": tool_name,
                    "status": "success",
                    "latency_ms": latency_ms,
                    "result": result_dict,
                })

                # Update working memory with latest result
                update_last_tool_result(state, tool_name, result_dict)

                # Update entities with tool output fields (for downstream tools)
                if isinstance(result_dict, dict):
                    for key, val in result_dict.items():
                        if val is not None and isinstance(val, (str, int, float)):
                            entities[key] = str(val)

                # Increment metrics
                if metrics:
                    metrics.tool_calls_made += 1

                # Update flags based on tool results
                flags = state.get("flags")
                if flags:
                    if tool_name == "create_ticket":
                        flags.ticket_created = True
                    elif tool_name in ("book_surveyor", "schedule_inspection"):
                        flags.engineer_booked = True
                    elif tool_name == "initiate_refund":
                        flags.refund_triggered = True

                logger.info(
                    "Tool executed successfully",
                    session_id=session_id,
                    node="tool_caller",
                    tool_name=tool_name,
                    latency_ms=latency_ms,
                    attempt=attempt + 1,
                )

                # Langfuse span
                if langfuse and langfuse.is_enabled:
                    await langfuse.create_span(
                        trace_id=session_id,
                        name=f"tool:{tool_name}",
                        input=input_data_dict,
                        output=result_dict,
                        metadata={"latency_ms": latency_ms},
                    )

                last_error = None
                break

            except Exception as e:
                last_error = e
                logger.warning(
                    "Tool execution failed, retrying",
                    session_id=session_id,
                    node="tool_caller",
                    tool_name=tool_name,
                    attempt=attempt + 1,
                    error=str(e),
                )

        if last_error:
            tool_results.append({
                "tool": tool_name,
                "status": "failed",
                "result": {"error": str(last_error)},
            })
            logger.error(
                "Tool failed after retry",
                session_id=session_id,
                node="tool_caller",
                tool_name=tool_name,
                error=str(last_error),
            )

    state["tool_results"] = tool_results
    return state
