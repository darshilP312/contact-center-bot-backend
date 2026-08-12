from __future__ import annotations

import re
from typing import Any

import yaml

from app.core.logging import get_logger

logger = get_logger("orchestrator.guardrails")

# PII masking patterns
_PII_PATTERNS = [
    (re.compile(r"\b\d{10}\b"), "[PHONE_REDACTED]"),                    # 10-digit phone
    (re.compile(r"\b\+91[-\s]?\d{10}\b"), "[PHONE_REDACTED]"),          # +91 phone
    (re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\b"), "[CARD_REDACTED]"),  # 16-digit card
    (re.compile(r"\bACC[-\s]?[A-Z0-9]{4,}\b"), "[ACCOUNT_REDACTED]"),  # Account numbers
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "[PAN_REDACTED]"),          # PAN card
    (re.compile(r"\b\d{12}\b"), "[AADHAAR_REDACTED]"),                   # Aadhaar
]


def _mask_pii(text: str) -> str:
    """Apply PII masking to text using regex patterns."""
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _load_policy_rules(domain_loader: Any, domain: str) -> list[dict]:
    """Load combined global + domain-specific policy rules."""
    import os
    from pathlib import Path

    rules = []

    # Global rules
    global_rules_path = Path(__file__).parent.parent.parent / "policies" / "global_rules.yaml"
    if global_rules_path.exists():
        with open(global_rules_path, encoding="utf-8") as f:
            global_config = yaml.safe_load(f) or {}
        rules.extend(global_config.get("rules", []))

    # Domain rules
    if domain_loader:
        domain_config = domain_loader.get_domain(domain) or {}
        # We don't load policies here directly — delegated to policy engine
        pass

    return rules


def _evaluate_condition(condition: dict, state: dict[str, Any]) -> bool:
    """Evaluate a single policy rule condition against the current state."""
    field = condition.get("field", "")
    operator = condition.get("operator", "equals")
    value = condition.get("value")

    # Navigate dot-notation path in state
    def get_nested(obj, path: str):
        parts = path.split(".")
        current = obj
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return None
        return current

    actual = get_nested(state, field)

    if operator == "equals":
        return actual == value
    elif operator == "not_equals":
        return actual != value
    elif operator == "gte":
        try:
            return float(actual or 0) >= float(value)
        except (TypeError, ValueError):
            return False
    elif operator == "lte":
        try:
            return float(actual or 0) <= float(value)
        except (TypeError, ValueError):
            return False
    elif operator == "length_gte":
        try:
            return len(actual or []) >= int(value)
        except (TypeError, ValueError):
            return False
    elif operator == "contains":
        return value in (actual or [])

    return False


async def guardrails_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    Guardrails Node — maps to diagram node X (Policy & Guardrails).

    Responsibilities:
    1. PII masking: replace phone/account/ID numbers in transcript with [REDACTED]
    2. Evaluate all three Decision Engine hard rules via PolicyEngine
    3. Evaluate global + domain YAML policy rules
    4. Set policy_violations, policy_evaluations, should_escalate, escalation_reason
    5. Emit agent.thinking WebSocket event

    Input:  Full AgentState (raw_transcript, conversation, customer, intent)
    Output: pii_masked_transcript, policy_violations, policy_evaluations,
            should_escalate, escalation_reason, flags
    """
    session_id = state.get("session_id", "none")
    ws = state.get("_ws_connection")
    domain_loader = state.get("_domain_loader")
    domain = state.get("domain", "insurance")

    if ws:
        await ws.send_json("agent.thinking", {"node": "guardrails", "status": "running"})

    # 1. PII masking
    raw_transcript = state.get("raw_transcript", "")
    masked = _mask_pii(raw_transcript)
    state["pii_masked_transcript"] = masked

    violations: list[str] = []
    should_escalate = state.get("should_escalate", False)
    escalation_reason = state.get("escalation_reason")
    policy_evals: list[dict] = list(state.get("policy_evaluations") or [])

    conversation = state.get("conversation")
    customer = state.get("customer")
    intent = state.get("intent")
    flags = state.get("flags")

    # 2. Decision Engine hard rules — evaluated first via PolicyEngine
    from app.policies.engine import PolicyEngine as _PE
    _pe = _PE()
    _pe.load_global_rules()

    de_triggered, de_rule_id, de_action = _pe.evaluate_hard_rules(state)
    if de_triggered and de_rule_id:
        violations.append(de_rule_id)
        rule_label = {
            "DE-001": "Angry/Frustrated Sentiment Escalation",
            "DE-002": "High-Value Refund Manager Approval Gate",
            "DE-003": "Diagnostic Failure Limit",
        }.get(de_rule_id, de_rule_id)
        policy_evals.append({
            "rule_checked": f"{de_rule_id}: {rule_label}",
            "passed": False,
            "action_taken": de_action or "escalate",
        })
        if de_action == "escalate":
            should_escalate = True
            sentiment = conversation.sentiment if conversation else "neutral"
            turn_count = conversation.turn_count if conversation else 0
            failed_diag = state.get("failed_diagnostics_count", 0)
            if de_rule_id == "DE-001":
                escalation_reason = f"Customer sentiment '{sentiment}' after {turn_count} turns — mandatory supervisor transfer"
            elif de_rule_id == "DE-003":
                escalation_reason = f"Diagnostic failure count {failed_diag} >= 3 — engineer visit required"
        elif de_action == "request_approval":
            state["manager_approval_required"] = True
            if flags:
                flags.awaiting_approval = True

    # 3. Legacy hard guards (urgent sentiment, verification gate)
    if conversation and conversation.sentiment == "urgent":
        if "GLOBAL_ESCALATION_002" not in violations:
            should_escalate = True
            escalation_reason = "Customer expressed urgent situation"
            violations.append("GLOBAL_ESCALATION_002")
            policy_evals.append({"rule_checked": "GLOBAL_003: Urgent Sentiment", "passed": False, "action_taken": "escalate"})

    # Guard: unverified customer attempting transaction tools
    transaction_tools = {
        "file_claim", "process_payment", "initiate_refund", "lookup_premium",
        "book_surveyor", "schedule_inspection", "cancel_order", "book_engineer",
    }
    tools_to_call = set(state.get("tools_to_call", []))
    if customer and not customer.verified and bool(tools_to_call & transaction_tools):
        violations.append("GLOBAL_VERIFICATION_001")
        policy_evals.append({"rule_checked": "GLOBAL_002: Verification Gate", "passed": False, "action_taken": "block"})
        state["tools_to_call"] = ["verify_customer"]

    # 4. Domain policy rules (loaded from YAML)
    if domain_loader:
        domain_config = domain_loader.get_domain(domain) or {}
        escalation_config = domain_config.get("escalation_config", {})
        max_turns = escalation_config.get("max_turns", 10)

        if conversation and conversation.turn_count > max_turns:
            should_escalate = True
            escalation_reason = f"Session exceeded {max_turns} turns without resolution"
            violations.append("DOMAIN_ESCALATION_001")
            policy_evals.append({"rule_checked": "GLOBAL_001: Max Session Length", "passed": False, "action_taken": "escalate"})

    state["policy_violations"] = violations
    state["should_escalate"] = should_escalate
    state["escalation_reason"] = escalation_reason
    state["policy_evaluations"] = policy_evals

    if violations:
        logger.info(
            "Policy violations detected",
            session_id=session_id,
            node="guardrails",
            violations=violations,
            should_escalate=should_escalate,
        )

    return state
