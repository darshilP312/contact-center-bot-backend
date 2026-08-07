"""
engine.py — Deterministic Policy Engine.
Evaluates business rules BEFORE any tool executes.
The LLM is NEVER consulted. Rules fire based on state values only.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PolicyVerdict:
    """Result of a policy evaluation."""
    blocked: bool
    reason: str = ""
    required_action: dict = field(default_factory=dict)


class PolicyEngine:
    """
    Evaluates all business rules in priority order.
    Returns the first blocking verdict found, or an allow verdict.

    Rules are checked in this order:
      P001 — Large refund
      P002 — Angry customer
      P003 — Diagnostic exhaustion
      P004 — Unverified customer on financial tool
      P005 — Repeated step failures
    """

    def evaluate(self, action: dict, state: dict) -> dict:
        """
        Main entry point.

        Args:
            action: The planned action dict from the plan node.
            state:  The current ConversationState as a dict.

        Returns:
            Plain dict: {"blocked": bool, "reason": str, "required_action": dict|None}
        """
        for rule in [
            self._p001_large_refund,
            self._p002_angry_customer,
            self._p003_diagnostic_exhaustion,
            self._p004_unverified_financial,
            self._p005_repeated_failures,
        ]:
            verdict = rule(action, state)
            if verdict.blocked:
                return {
                    "blocked": True,
                    "reason": verdict.reason,
                    "required_action": verdict.required_action,
                }

        return {"blocked": False, "reason": "", "required_action": None}

    # ── P001 — Large Refund ───────────────────────────────────────────────────

    def _p001_large_refund(self, action: dict, state: dict) -> PolicyVerdict:
        """Refund > Rs.10,000 requires manager approval."""
        if action.get("tool_name") != "refund_payment":
            return PolicyVerdict(blocked=False)

        amount = float(action.get("tool_args", {}).get("amount", 0))
        if amount > 10_000:
            return PolicyVerdict(
                blocked=True,
                reason=f"P001: Refund of Rs.{amount:,.0f} exceeds Rs.10,000 limit.",
                required_action={
                    "kind": "await_approval",
                    "message": (
                        f"This refund of Rs.{amount:,.0f} requires manager approval. "
                        "I've escalated this and you'll receive a confirmation within 24 hours."
                    ),
                    "escalation_tier": "manager",
                },
            )
        return PolicyVerdict(blocked=False)

    # ── P002 — Angry Customer ─────────────────────────────────────────────────

    def _p002_angry_customer(self, action: dict, state: dict) -> PolicyVerdict:
        """Customer sentiment 'angry' triggers immediate human escalation."""
        already_escalated = state.get("flags", {}).get("escalated", False)
        action_kind = action.get("kind", "")

        if (
            state.get("sentiment") == "angry"
            and not already_escalated
            and action_kind not in ("escalate", "ask")
        ):
            return PolicyVerdict(
                blocked=True,
                reason="P002: Customer sentiment is 'angry'. Escalating to human agent.",
                required_action={
                    "kind": "escalate",
                    "message": (
                        "I completely understand your frustration and I sincerely apologise "
                        "for the experience you've had. Let me connect you with a senior "
                        "specialist right away who can resolve this for you."
                    ),
                },
            )
        return PolicyVerdict(blocked=False)

    # ── P003 — Diagnostic Exhaustion ─────────────────────────────────────────

    def _p003_diagnostic_exhaustion(self, action: dict, state: dict) -> PolicyVerdict:
        """After 3 failed diagnostics, force an engineer visit."""
        if action.get("tool_name") != "run_diagnostics":
            return PolicyVerdict(blocked=False)

        diag_run = state.get("working_memory", {}).get("diagnostics_run", 0)
        if diag_run >= 3:
            return PolicyVerdict(
                blocked=True,
                reason=f"P003: {diag_run} diagnostic attempts exhausted. Engineer visit required.",
                required_action={
                    "kind": "tool",
                    "tool_name": "book_engineer",
                    "tool_args": {
                        "reason": f"{diag_run} remote diagnostics failed",
                        "priority": "high",
                    },
                    "message": (
                        "We've attempted remote diagnostics three times and the issue persists. "
                        "I'm arranging a priority engineer visit for you as the next step."
                    ),
                },
            )
        return PolicyVerdict(blocked=False)

    # ── P004 — Unverified Customer on Financial Tool ──────────────────────────

    def _p004_unverified_financial(self, action: dict, state: dict) -> PolicyVerdict:
        """Financial tools require verified customer identity."""
        financial_tools = {"refund_payment", "lookup_invoice", "cancel_order"}
        if (
            action.get("tool_name") in financial_tools
            and not state.get("customer", {}).get("verified", False)
        ):
            return PolicyVerdict(
                blocked=True,
                reason="P004: Customer not verified. Cannot execute financial tool.",
                required_action={
                    "kind": "tool",
                    "tool_name": "lookup_customer",
                    "tool_args": {},
                    "message": (
                        "Before I can process this for you, I need to verify your account. "
                        "Could you please share your account number or registered phone number?"
                    ),
                },
            )
        return PolicyVerdict(blocked=False)

    # ── P005 — Repeated Step Failures ────────────────────────────────────────

    def _p005_repeated_failures(self, action: dict, state: dict) -> PolicyVerdict:
        """After 2 failed attempts at the same step, escalate."""
        current_step = state.get("workflow", {}).get("step", "")
        step_attempts = state.get("workflow", {}).get("step_attempts", {})
        attempts = step_attempts.get(current_step, 0)

        if attempts >= 2 and action.get("kind") == "tool":
            tool_name = action.get("tool_name", "unknown")
            return PolicyVerdict(
                blocked=True,
                reason=f"P005: Tool '{tool_name}' failed {attempts} times at step '{current_step}'.",
                required_action={
                    "kind": "escalate",
                    "message": (
                        "I'm having difficulty resolving this automatically. "
                        "Let me get a specialist on the line who can help you directly."
                    ),
                },
            )
        return PolicyVerdict(blocked=False)
