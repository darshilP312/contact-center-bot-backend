from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from app.core.config import get_settings
from app.core.logging import get_logger
from app.orchestrator.nodes.business_router import business_router_node
from app.orchestrator.nodes.conversation_understanding import conversation_understanding_node
from app.orchestrator.nodes.escalation_handler import escalation_handler_node
from app.orchestrator.nodes.guardrails import guardrails_node
from app.orchestrator.nodes.planner import planner_node
from app.orchestrator.nodes.rag import rag_node
from app.orchestrator.nodes.response_generator import response_generator_node
from app.orchestrator.nodes.tool_caller import tool_caller_node
from app.orchestrator.nodes.workflow_executor import workflow_executor_node

logger = get_logger("orchestrator.graph")
settings = get_settings()

# ─── Runtime references injected into state ───────────────────────────────────
# Each graph invocation receives these via the state dict under _-prefixed keys.
# They are not serialised to Redis (only pure-data fields are persisted).


def _inject_runtime(state: dict[str, Any], **kwargs) -> dict[str, Any]:
    """Inject runtime-only references into state before graph invocation."""
    return {**state, **kwargs}


# ─── Edge routing functions ────────────────────────────────────────────────────

def route_after_guardrails(state: dict[str, Any]) -> str:
    """
    Route after guardrails evaluation.

    - should_escalate=True → escalation_handler → END
    - otherwise → business_router
    """
    if state.get("should_escalate"):
        return "escalation_handler"
    return "business_router"


def route_after_planner(state: dict[str, Any]) -> str:
    """
    Route after planner decision.

    - clarification_needed=True → response_generator (ask question)
    - requires_rag=True AND no tools → rag
    - tools_to_call non-empty → tool_caller
    - otherwise → response_generator (general response)
    """
    if state.get("clarification_needed"):
        return "response_generator"
    if state.get("requires_rag") and not state.get("tools_to_call"):
        return "rag"
    if state.get("tools_to_call"):
        return "tool_caller"
    return "response_generator"


def route_after_tool_caller(state: dict[str, Any]) -> str:
    """After tool calls, advance the workflow before generating response."""
    if state.get("workflow") and state["workflow"].name:
        return "workflow_executor"
    return "response_generator"


def route_after_response_generator(state: dict[str, Any]) -> str:
    """
    Reasoning loop control — after generating a response, decide whether to
    loop back to the planner for more work.

    Loop conditions (ALL must be true):
    1. loop_count < max_loops
    2. A workflow is active AND has a pending (non-completed) next step
    3. Tools were called in the most recent planner turn (prevents RAG loops)

    RAG-only and clarification turns always go to END immediately.
    """
    loop_count = state.get("loop_count", 0)
    max_loops = settings.PLANNER_MAX_LOOP_COUNT

    # Never loop on clarification or RAG-only turns
    if state.get("clarification_needed"):
        return END
    if state.get("requires_rag") and not state.get("tool_results"):
        return END

    workflow = state.get("workflow")

    # Only continue if:
    # 1. There is an active workflow with a NEXT step (step != None means more work to do)
    # 2. Tools were actually called this turn (not a pure-informational answer)
    # 3. Loop budget not exhausted
    tools_were_called = bool(state.get("tool_results"))
    has_next_workflow_step = (
        workflow is not None
        and workflow.name
        and workflow.step is not None  # None means workflow is complete
    )

    if has_next_workflow_step and tools_were_called and loop_count < max_loops:
        return "planner"

    return END


def route_after_rag(state: dict[str, Any]) -> str:
    """After RAG retrieval, always go to response_generator."""
    return "response_generator"


# ─── Graph Builder ─────────────────────────────────────────────────────────────

def build_graph(
    ws_connection: Any,
    domain_loader: Any,
    tool_registry: Any,
    rag_node: Any,
    stt: Any,
    tts: Any,
    langfuse: Any,
) -> Any:
    """
    Build and compile the LangGraph StateGraph.

    The graph is compiled fresh per invocation (lightweight in LangGraph).
    Runtime references are passed as state keys to avoid global state.

    Graph topology:
    START
      → conversation_understanding
      → planner
      → guardrails
      → (escalation_handler → END) | business_router
      → (rag → response_generator) | (tool_caller → workflow_executor → response_generator) | response_generator
      → (planner loop if workflow remaining) | END

    Args:
        ws_connection: Active WebSocket connection for event emission.
        domain_loader: DomainLoader instance.
        tool_registry: ToolRegistry instance.
        rag_node: RAGNode instance.
        stt: STT provider.
        tts: TTS provider.
        langfuse: Langfuse client.

    Returns:
        Compiled LangGraph graph ready for ainvoke().
    """
    # Wrap each node to inject runtime references before execution
    runtime_refs = {
        "_ws_connection": ws_connection,
        "_domain_loader": domain_loader,
        "_tool_registry": tool_registry,
        "_rag_node": rag_node,
        "_tts": tts,
        "_langfuse": langfuse,
    }

    async def cu_node(state):
        return await conversation_understanding_node({**state, **runtime_refs})

    async def plan_node(state):
        return await planner_node({**state, **runtime_refs})

    async def gr_node(state):
        return await guardrails_node({**state, **runtime_refs})

    async def br_node(state):
        return await business_router_node({**state, **runtime_refs})

    async def r_node(state):
        from app.orchestrator.nodes.rag import rag_node as _rag_node_fn
        return await _rag_node_fn({**state, **runtime_refs})

    async def tc_node(state):
        return await tool_caller_node({**state, **runtime_refs})

    async def we_node(state):
        return await workflow_executor_node({**state, **runtime_refs})

    async def rg_node(state):
        return await response_generator_node({**state, **runtime_refs})

    async def esc_node(state):
        return await escalation_handler_node({**state, **runtime_refs})

    # Build the graph
    builder = StateGraph(dict)

    # Add nodes
    builder.add_node("conversation_understanding", cu_node)
    builder.add_node("planner", plan_node)
    builder.add_node("guardrails", gr_node)
    builder.add_node("business_router", br_node)
    builder.add_node("rag", r_node)
    builder.add_node("tool_caller", tc_node)
    builder.add_node("workflow_executor", we_node)
    builder.add_node("response_generator", rg_node)
    builder.add_node("escalation_handler", esc_node)

    # Linear edges
    builder.add_edge(START, "conversation_understanding")
    builder.add_edge("conversation_understanding", "planner")
    builder.add_edge("planner", "guardrails")

    # Conditional edges
    builder.add_conditional_edges(
        "guardrails",
        route_after_guardrails,
        {
            "escalation_handler": "escalation_handler",
            "business_router": "business_router",
        },
    )

    builder.add_conditional_edges(
        "business_router",
        route_after_planner,  # Re-evaluate planner outputs after routing
        {
            "rag": "rag",
            "tool_caller": "tool_caller",
            "response_generator": "response_generator",
        },
    )

    builder.add_conditional_edges(
        "tool_caller",
        route_after_tool_caller,
        {
            "workflow_executor": "workflow_executor",
            "response_generator": "response_generator",
        },
    )

    builder.add_edge("workflow_executor", "response_generator")
    builder.add_edge("rag", "response_generator")

    builder.add_conditional_edges(
        "response_generator",
        route_after_response_generator,
        {
            "planner": "planner",
            END: END,
        },
    )

    builder.add_edge("escalation_handler", END)

    return builder.compile()
