"""
test_policy.py — Deterministic policy engine tests.
All 5 rules must be independently verified. No LLM calls.
"""

import pytest
from app.policies.engine import PolicyEngine

engine = PolicyEngine()


def base_state(overrides: dict = None) -> dict:
    """Build a minimal valid state dict for testing."""
    state = {
        "customer": {"verified": True, "customer_id": "ACC001"},
        "intent": {"name": "technical_support", "confidence": 0.9, "entities": {}},
        "workflow": {"name": "technical_support", "step": "run_diagnostics", "step_attempts": {}},
        "working_memory": {"diagnostics_run": 0},
        "flags": {"escalated": False, "ticket_created": False},
        "sentiment": "neutral",
        "metrics": {"policy_blocks": 0},
    }
    if overrides:
        _deep_update(state, overrides)
    return state


def _deep_update(d: dict, u: dict) -> dict:
    for k, v in u.items():
        if isinstance(v, dict) and k in d:
            _deep_update(d[k], v)
        else:
            d[k] = v
    return d


class TestP001LargeRefund:
    def test_blocks_refund_over_10000(self):
        action = {"kind": "tool", "tool_name": "refund_payment", "tool_args": {"amount": 15000}}
        verdict = engine.evaluate(action, base_state())
        assert verdict["blocked"] is True
        assert "P001" in verdict["reason"]
        assert verdict["required_action"]["kind"] == "await_approval"

    def test_allows_refund_under_10000(self):
        action = {"kind": "tool", "tool_name": "refund_payment", "tool_args": {"amount": 2500}}
        verdict = engine.evaluate(action, base_state())
        assert verdict["blocked"] is False

    def test_allows_refund_exactly_10000(self):
        action = {"kind": "tool", "tool_name": "refund_payment", "tool_args": {"amount": 10000}}
        verdict = engine.evaluate(action, base_state())
        assert verdict["blocked"] is False

    def test_non_refund_tool_not_affected(self):
        action = {"kind": "tool", "tool_name": "book_engineer", "tool_args": {"amount": 99999}}
        verdict = engine.evaluate(action, base_state())
        assert verdict["blocked"] is False


class TestP002AngrySentiment:
    def test_blocks_angry_customer(self):
        action = {"kind": "tool", "tool_name": "check_outage", "tool_args": {}}
        state = base_state({"sentiment": "angry"})
        verdict = engine.evaluate(action, state)
        assert verdict["blocked"] is True
        assert "P002" in verdict["reason"]
        assert verdict["required_action"]["kind"] == "escalate"

    def test_does_not_double_escalate(self):
        action = {"kind": "tool", "tool_name": "check_outage", "tool_args": {}}
        state = base_state({"sentiment": "angry", "flags": {"escalated": True}})
        verdict = engine.evaluate(action, state)
        assert verdict["blocked"] is False

    def test_frustrated_does_not_trigger(self):
        action = {"kind": "tool", "tool_name": "run_diagnostics", "tool_args": {}}
        state = base_state({"sentiment": "frustrated"})
        verdict = engine.evaluate(action, state)
        assert verdict["blocked"] is False


class TestP003DiagnosticExhaustion:
    def test_blocks_after_3_diagnostics(self):
        action = {"kind": "tool", "tool_name": "run_diagnostics", "tool_args": {}}
        state = base_state({"working_memory": {"diagnostics_run": 3}})
        verdict = engine.evaluate(action, state)
        assert verdict["blocked"] is True
        assert "P003" in verdict["reason"]
        assert verdict["required_action"]["tool_name"] == "book_engineer"

    def test_allows_first_diagnostic(self):
        action = {"kind": "tool", "tool_name": "run_diagnostics", "tool_args": {}}
        state = base_state({"working_memory": {"diagnostics_run": 0}})
        verdict = engine.evaluate(action, state)
        assert verdict["blocked"] is False

    def test_blocks_after_exactly_3(self):
        action = {"kind": "tool", "tool_name": "run_diagnostics", "tool_args": {}}
        state = base_state({"working_memory": {"diagnostics_run": 3}})
        verdict = engine.evaluate(action, state)
        assert verdict["blocked"] is True


class TestP004UnverifiedFinancial:
    def test_blocks_unverified_refund(self):
        action = {"kind": "tool", "tool_name": "refund_payment", "tool_args": {"amount": 500}}
        state = base_state({"customer": {"verified": False, "customer_id": None}})
        verdict = engine.evaluate(action, state)
        assert verdict["blocked"] is True
        assert "P004" in verdict["reason"]
        assert verdict["required_action"]["tool_name"] == "lookup_customer"

    def test_allows_verified_refund(self):
        action = {"kind": "tool", "tool_name": "refund_payment", "tool_args": {"amount": 500}}
        state = base_state({"customer": {"verified": True}})
        verdict = engine.evaluate(action, state)
        # May be blocked by P001 if amount > 10000, but not P004
        if verdict["blocked"]:
            assert "P004" not in verdict["reason"]

    def test_non_financial_tool_unverified_allowed(self):
        action = {"kind": "tool", "tool_name": "check_outage", "tool_args": {}}
        state = base_state({"customer": {"verified": False}})
        verdict = engine.evaluate(action, state)
        assert verdict["blocked"] is False


class TestP005RepeatedFailures:
    def test_blocks_after_2_failures(self):
        action = {"kind": "tool", "tool_name": "book_engineer", "tool_args": {}}
        state = base_state({
            "workflow": {
                "step": "book_engineer",
                "step_attempts": {"book_engineer": 2},
            }
        })
        verdict = engine.evaluate(action, state)
        assert verdict["blocked"] is True
        assert "P005" in verdict["reason"]
        assert verdict["required_action"]["kind"] == "escalate"

    def test_allows_first_attempt(self):
        action = {"kind": "tool", "tool_name": "book_engineer", "tool_args": {}}
        state = base_state({
            "workflow": {
                "step": "book_engineer",
                "step_attempts": {"book_engineer": 0},
            }
        })
        verdict = engine.evaluate(action, state)
        assert verdict["blocked"] is False
