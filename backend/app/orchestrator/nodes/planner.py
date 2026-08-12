from __future__ import annotations

import json
from typing import Any, Literal

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.llm.client import LLMClient

logger = get_logger("orchestrator.planner")
settings = get_settings()
_llm = LLMClient()

# ── Business rule constants ────────────────────────────────────────────────────
REFUND_MANAGER_APPROVAL_THRESHOLD_INR = 10_000.0   # Rule DE-002
MAX_FAILED_DIAGNOSTICS = 3                          # Rule DE-003
SENTIMENT_ESCALATION_TURN_THRESHOLD = 6            # Rule DE-001

# Intent types as constants (matches Decision Engine output schema)
INTENT_INFORMATIONAL_RAG = "INFORMATIONAL_RAG"
INTENT_ACTIONAL_WORKFLOW = "ACTIONAL_WORKFLOW"
INTENT_DIAGNOSTIC_ACTION = "DIAGNOSTIC_ACTION"

# Tools that are pure-informational (RAG path only, never transactional)
INFORMATIONAL_INTENTS = {
    "faq_query",
    "policy_inquiry",
    "product_info",
    "eligibility_check",
    "document_requirements",
    "coverage_inquiry",
    "claim_process_query",
    "general_query",
}

# Tools that require customer verification before execution
TRANSACTION_TOOLS = {
    "process_payment",
    "initiate_refund",
    "file_claim",
    "cancel_order",
    "book_engineer",
    "book_surveyor",
    "schedule_inspection",
    "assign_surveyor",
    "create_ticket",
}


def _build_decision_engine_prompt(
    domain: str,
    customer_id: str,
    is_verified: bool,
    sentiment: str,
    turn_count: int,
    failed_diagnostics_count: int,
    rag_context: str,
    tool_results_str: str,
    transcript: str,
    tool_manifest: list,
    intent_name: str,
    entities: dict,
    missing_entities: list,
    history_str: str,
    workflow_name: str | None,
    workflow_step: str | None,
    completed_steps: list,
    loop_count: int,
) -> str:
    """Build the canonical Decision Engine system prompt."""
    return f"""You are the central Intelligence and Decision Engine of the Enterprise Voice-First AI Command Center.
Your core mission is to assist customers accurately, process business workflows seamlessly, and strictly adhere to corporate policy guardrails without EVER hallucinating rules or taking unauthorized actions.

===============================================================================
OPERATIONAL DIRECTIVES AND BOUNDARIES
===============================================================================

1. INTENT SEPARATION AND RAG USAGE RULES:
   For INFORMATIONAL QUERIES (e.g., "What is the refund policy?", "How long is the warranty?", "What documents are required?"):
     - Set intent_type = "INFORMATIONAL_RAG".
     - Rely EXCLUSIVELY on the retrieved RAG context provided under GROUND_TRUTH_KNOWLEDGE.
     - DO NOT execute, suggest, or trigger any transactional tools.
     - If information is missing from GROUND_TRUTH_KNOWLEDGE, state clearly: "I do not have specific policy details regarding that in my knowledge base. Let me connect you with a specialist."

   For ACTIONABLE / TRANSACTION REQUESTS (e.g., "Refund my payment", "Book an engineer visit", "Cancel order"):
     - Set intent_type = "ACTIONAL_WORKFLOW".
     - DO NOT invoke RAG or retrieve knowledge articles.
     - Identify required parameters (order_id, amount, account_number, reason).
     - Verify customer identity (customer.verified == true) before initiating any action tool.

   For DIAGNOSTIC ACTIONS (e.g., troubleshooting, software resets, technical steps):
     - Set intent_type = "DIAGNOSTIC_ACTION".

2. POLICY ENGINE AND BUSINESS RULE GOVERNANCE (THESE ARE ABSOLUTE — NEVER OVERRIDE):
   RULE DE-002 — Monetary Gate: Any refund amount GREATER THAN OR EQUAL TO INR 10,000 CANNOT be automatically processed.
     You MUST set tools_to_call = ["create_manager_approval_ticket"] instead of process_refund. No exceptions.
   RULE DE-001 — Sentiment Escalation: If sentiment is "angry" or "frustrated" AND turn_count >= {SENTIMENT_ESCALATION_TURN_THRESHOLD}, OR if the customer explicitly requests human transfer, trigger escalation immediately.
   RULE DE-003 — Diagnostic Limit: If failed_diagnostics_count >= {MAX_FAILED_DIAGNOSTICS}, do NOT run further software troubleshooting. Immediately transition to schedule_engineer_visit.
   RULE GLOBAL-002 — Verification Gate: Any transaction tool requires customer.verified == true. Call verify_customer first if unverified.

3. RESPONSE FORMAT AND VOICE CONSTRAINTS:
   - Keep answers concise, natural, and friendly for voice (1 to 3 sentences maximum per turn).
   - NEVER output markdown symbols like asterisks (*), hashtags (#), or bullet points in customer_response_text.
   - Always cite official sources for policy questions (e.g., "According to our Warranty Policy...").
   - customer_response_text must be complete and standalone — it will be sent directly to TTS.

===============================================================================
CURRENT CONTEXT
===============================================================================
Customer ID: {customer_id} | Verified: {is_verified}
Active Domain: {domain}
Conversation Sentiment: {sentiment} | Turn Count: {turn_count}
Failed Diagnostics Count: {failed_diagnostics_count}

GROUND_TRUTH_KNOWLEDGE (RAG Retrieved):
{rag_context or "(No knowledge base content retrieved for this turn)"}

TOOL EXECUTION RESULTS:
{tool_results_str or "(No tool calls made yet)"}

CURRENT WORKFLOW STATE:
- Active Workflow: {workflow_name or "None"}
- Current Step: {workflow_step or "None"}
- Completed Steps: {completed_steps}
- Detected Intent: {intent_name} | Entities Collected: {json.dumps(entities)}
- Missing Required Entities: {missing_entities}
- Planner Loop: {loop_count}

RECENT CONVERSATION HISTORY:
{history_str or "(First turn — no prior history)"}

AVAILABLE TOOLS FOR DOMAIN "{domain}":
{json.dumps(tool_manifest, indent=2)}

LATEST CUSTOMER UTTERANCE: "{transcript}"

===============================================================================
OUTPUT SCHEMA — Return ONLY valid JSON, no commentary, no markdown
===============================================================================
{{
  "intent_type": "INFORMATIONAL_RAG | ACTIONAL_WORKFLOW | DIAGNOSTIC_ACTION",
  "reasoning": "Brief technical rationale for decision (1-2 sentences, internal only)",
  "policy_evaluations": [
    {{
      "rule_checked": "Rule ID or description",
      "passed": true,
      "action_taken": "proceed | block | escalate | request_approval"
    }}
  ],
  "requires_rag": false,
  "missing_entities": [],
  "tools_to_call": ["ordered list of tool names — executed sequentially"],
  "clarification_needed": false,
  "clarification_question": null,
  "customer_response_text": "Spoken response text. No markdown. 1-3 sentences maximum."
}}

DECISION RULES (apply in this order):
1. Check RULE DE-001: if sentiment in (angry, frustrated) AND turn_count >= {SENTIMENT_ESCALATION_TURN_THRESHOLD} → tools_to_call=["route_to_human_agent"], action_taken="escalate"
2. Check RULE DE-003: if failed_diagnostics_count >= {MAX_FAILED_DIAGNOSTICS} → tools_to_call=["schedule_engineer_visit"], action_taken="escalate"
3. Classify intent_type based on the customer utterance
4. If INFORMATIONAL_RAG: set requires_rag=true, tools_to_call=[]
5. If ACTIONAL_WORKFLOW or DIAGNOSTIC_ACTION:
   a. If customer not verified → tools_to_call=["verify_customer"]
   b. If refund amount >= INR 10000 → tools_to_call=["create_manager_approval_ticket"], action_taken="request_approval"
   c. If missing required entities → clarification_needed=true, ask for the first missing entity
   d. Otherwise → tools_to_call with appropriate domain tools in order"""


async def planner_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    Planner / Decision Engine Node — maps to diagram node L (LLM Reasoner).

    Implements the canonical Decision Engine system prompt with:
    - Intent separation (INFORMATIONAL_RAG vs ACTIONAL_WORKFLOW vs DIAGNOSTIC_ACTION)
    - Three absolute business rules (monetary gate, sentiment escalation, diagnostic limit)
    - Typed output schema with policy_evaluations audit log
    - Voice-safe customer_response_text (no markdown, ≤3 sentences)

    Input:  Full AgentState
    Output: intent_type, requires_rag, tools_to_call, clarification_needed,
            clarification_question, policy_evaluations, missing_entities, loop_count++
    """
    session_id = state.get("session_id", "none")
    ws = state.get("_ws_connection")
    domain_loader = state.get("_domain_loader")
    tool_registry = state.get("_tool_registry")

    if ws:
        await ws.send_json("agent.thinking", {"node": "planner", "status": "running"})

    # Increment loop count
    loop_count = state.get("loop_count", 0) + 1
    state["loop_count"] = loop_count

    # Unpack context
    intent = state.get("intent")
    conversation = state.get("conversation")
    customer = state.get("customer")
    workflow = state.get("workflow")
    domain = state.get("domain", "insurance")
    transcript = state.get("pii_masked_transcript", state.get("raw_transcript", ""))
    failed_diagnostics = state.get("failed_diagnostics_count", 0)
    refund_amount = state.get("refund_amount")

    # ── Pre-flight hard rule checks (before LLM call) ─────────────────────────
    # DE-001: Sentiment escalation (also handled in guardrails but authoritative here)
    sentiment = conversation.sentiment if conversation else "neutral"
    turn_count = conversation.turn_count if conversation else 0
    escalation_threshold = SENTIMENT_ESCALATION_TURN_THRESHOLD
    if domain_loader:
        dom_cfg = domain_loader.get_domain(domain) or {}
        escalation_threshold = dom_cfg.get("escalation_config", {}).get("max_turns", SENTIMENT_ESCALATION_TURN_THRESHOLD)

    if (sentiment == "angry" and turn_count >= escalation_threshold) or (sentiment == "frustrated" and turn_count >= escalation_threshold + 2):
        state["should_escalate"] = True
        state["escalation_reason"] = f"Sentiment '{sentiment}' with {turn_count} turns triggers mandatory escalation"
        state["intent_type"] = INTENT_ACTIONAL_WORKFLOW
        state["tools_to_call"] = ["route_to_human_agent"]
        state["policy_evaluations"] = [{
            "rule_checked": "DE-001: Sentiment Escalation",
            "passed": False,
            "action_taken": "escalate",
        }]
        logger.info("DE-001 triggered: sentiment escalation", session_id=session_id, sentiment=sentiment, turns=turn_count)
        return state

    # DE-003: Diagnostic limit
    if failed_diagnostics >= MAX_FAILED_DIAGNOSTICS:
        state["intent_type"] = INTENT_DIAGNOSTIC_ACTION
        state["tools_to_call"] = ["schedule_engineer_visit"]
        state["policy_evaluations"] = [{
            "rule_checked": "DE-003: Diagnostic Failure Limit",
            "passed": False,
            "action_taken": "escalate",
        }]
        logger.info("DE-003 triggered: diagnostic limit reached", session_id=session_id, count=failed_diagnostics)
        return state

    # ── Get domain context ─────────────────────────────────────────────────────
    intent_config: dict = {}
    if domain_loader and intent and intent.name:
        intent_config = domain_loader.get_intent(domain, intent.name) or {}

    required_entities = intent_config.get("required_entities", [])
    entities = intent.entities if intent else {}
    missing = [e for e in required_entities if e not in entities]

    enabled_tools: list = []
    if domain_loader:
        domain_config = domain_loader.get_domain(domain) or {}
        enabled_tools = domain_config.get("enabled_tools", [])

    tool_manifest: list = []
    if tool_registry:
        tool_manifest = tool_registry.get_manifest(domain, enabled_tools)

    # Build context strings
    history_str = "".join(
        f"{e.role.upper()}: {e.text}\n"
        for e in (state.get("transcript_history") or [])[-8:]
    )
    tool_results_str = "".join(
        f"- {tr.get('tool')}: {json.dumps(tr.get('result', {}))[:250]}\n"
        for tr in (state.get("tool_results") or [])[-5:]
        if tr.get("status") == "success"
    )

    # ── Call Decision Engine LLM ───────────────────────────────────────────────
    prompt = _build_decision_engine_prompt(
        domain=domain,
        customer_id=customer.customer_id or "unknown" if customer else "unknown",
        is_verified=customer.verified if customer else False,
        sentiment=sentiment,
        turn_count=turn_count,
        failed_diagnostics_count=failed_diagnostics,
        rag_context=state.get("rag_result") or "",
        tool_results_str=tool_results_str,
        transcript=transcript,
        tool_manifest=tool_manifest,
        intent_name=intent.name if intent else "unknown",
        entities=entities,
        missing_entities=missing,
        history_str=history_str,
        workflow_name=workflow.name if workflow else None,
        workflow_step=workflow.step if workflow else None,
        completed_steps=workflow.completed_steps if workflow else [],
        loop_count=loop_count,
    )

    result: dict = {}
    try:
        result = await _llm.structured_completion(
            messages=[{"role": "user", "content": prompt}],
            json_schema={},
            session_id=session_id,
            node="planner",
        )
    except Exception as e:
        logger.error("Decision Engine LLM call failed", session_id=session_id, node="planner", error=str(e))
        # Safe fallback
        result = {
            "intent_type": INTENT_INFORMATIONAL_RAG if not missing else INTENT_ACTIONAL_WORKFLOW,
            "reasoning": f"LLM unavailable: {e}",
            "policy_evaluations": [],
            "requires_rag": bool(intent_config.get("requires_rag", False)),
            "missing_entities": missing,
            "tools_to_call": [],
            "clarification_needed": bool(missing),
            "clarification_question": f"Could you please provide your {missing[0]}?" if missing else None,
            "customer_response_text": "",
        }

    # ── Parse and validate Decision Engine output ─────────────────────────────
    intent_type = result.get("intent_type", INTENT_ACTIONAL_WORKFLOW)
    if intent_type not in (INTENT_INFORMATIONAL_RAG, INTENT_ACTIONAL_WORKFLOW, INTENT_DIAGNOSTIC_ACTION):
        intent_type = INTENT_ACTIONAL_WORKFLOW

    policy_evaluations: list = result.get("policy_evaluations", [])

    # INFORMATIONAL_RAG must never have tools
    if intent_type == INTENT_INFORMATIONAL_RAG:
        tools = []
        requires_rag = True
    else:
        requires_rag = bool(result.get("requires_rag", False)) or bool(intent_config.get("requires_rag"))
        raw_tools = result.get("tools_to_call", [])
        # Enforce domain allowlist
        allowed = set(enabled_tools)
        tools = [t for t in raw_tools if t in allowed or t in {"route_to_human_agent", "verify_customer", "create_manager_approval_ticket", "schedule_engineer_visit"}]

    # ── DE-002: Monetary gate (post-LLM enforcement) ──────────────────────────
    if refund_amount is not None and refund_amount >= REFUND_MANAGER_APPROVAL_THRESHOLD_INR:
        if "process_refund" in tools or "initiate_refund" in tools:
            # Remove direct refund tools, replace with approval ticket
            tools = [t for t in tools if t not in ("process_refund", "initiate_refund")]
            if "create_manager_approval_ticket" not in tools:
                tools = ["create_manager_approval_ticket"] + tools
            state["manager_approval_required"] = True
            policy_evaluations.append({
                "rule_checked": "DE-002: Refund Monetary Gate (>= INR 10,000)",
                "passed": False,
                "action_taken": "request_approval",
            })
            logger.info(
                "DE-002 triggered: refund amount requires manager approval",
                session_id=session_id,
                refund_amount=refund_amount,
            )

    # ── Clarification ──────────────────────────────────────────────────────────
    clarification_needed = bool(result.get("clarification_needed", bool(missing and intent_type != INTENT_INFORMATIONAL_RAG)))
    clarification_question = result.get("clarification_question")

    # ── Store pre-generated customer response text (if LLM produced one) ──────
    response_text_draft = result.get("customer_response_text", "")
    if response_text_draft and not state.get("response_text"):
        # The planner optionally returns a pre-built response (mainly for clarification turns)
        # The response_generator node will still produce the final authoritative response,
        # but this serves as a seed/fallback.
        state["_planner_response_draft"] = response_text_draft

    # ── Write to state ─────────────────────────────────────────────────────────
    state["intent_type"] = intent_type
    state["requires_rag"] = requires_rag
    state["tools_to_call"] = tools
    state["clarification_needed"] = clarification_needed
    state["clarification_question"] = clarification_question
    state["missing_entities"] = result.get("missing_entities", missing)
    state["policy_evaluations"] = policy_evaluations

    # For RAG-only or clarification turns, reset tool_results so the loop
    # guard in route_after_response_generator doesn't mistake prior turns'
    # tool calls as "tools were called this turn".
    if intent_type == INTENT_INFORMATIONAL_RAG or clarification_needed:
        state["tool_results"] = []

    logger.info(
        "Decision Engine decision",
        session_id=session_id,
        node="planner",
        intent_type=intent_type,
        tools_to_call=tools,
        requires_rag=requires_rag,
        clarification_needed=clarification_needed,
        loop_count=loop_count,
        policy_evaluations=[p.get("rule_checked") for p in policy_evaluations],
    )

    # Emit WebSocket event with planner decision
    if ws:
        await ws.send_json(
            "planner.decision",
            {
                "intent_type": intent_type,
                "tools_to_call": tools,
                "requires_rag": requires_rag,
                "clarification_needed": clarification_needed,
                "policy_evaluations": policy_evaluations,
                "session_id": session_id,
            },
        )

    return state
