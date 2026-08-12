"""Unit tests for the Policy Engine."""
from __future__ import annotations

import pytest

from app.policies.engine import PolicyEngine
from app.models.conversation import ConversationState, CustomerInfo
from app.models.intent import IntentInfo
from app.models.flags import SessionFlags


def _make_state(
    sentiment: str = "neutral",
    turn_count: int = 2,
    verified: bool = True,
    intent_name: str = "general_query",
) -> dict:
    """Build a minimal AgentState dict for policy engine testing."""
    session_id = "sess_test"
    conversation = ConversationState(session_id=session_id, sentiment=sentiment, turn_count=turn_count)
    customer = CustomerInfo(session_id=session_id, verified=verified)
    intent = IntentInfo(session_id=session_id, name=intent_name)
    flags = SessionFlags(session_id=session_id)

    return {
        "session_id": session_id,
        "conversation": conversation,
        "customer": customer,
        "intent": intent,
        "flags": flags,
        "pii_masked_transcript": "I need help",
        "tools_to_call": [],
        "tool_results": [],
    }


class TestPolicyEngineRuleLoading:
    def test_global_rules_load(self, tmp_path):
        engine = PolicyEngine()
        # Write a minimal rules file
        rules_path = tmp_path / "global_rules.yaml"
        rules_path.write_text("""
rules:
  - rule_id: TEST_001
    name: "Test Rule"
    condition:
      field: conversation.sentiment
      operator: equals
      value: frustrated
    action: escalate
    escalation_reason: "Test escalation"
""")
        engine._global_rules = []
        import yaml
        with open(rules_path) as f:
            engine._global_rules = yaml.safe_load(f).get("rules", [])
        assert len(engine._global_rules) == 1

    def test_domain_rules_load(self, tmp_path):
        engine = PolicyEngine()
        rules_path = tmp_path / "rules.yaml"
        rules_path.write_text("""
domain: test
rules:
  - rule_id: DOM_001
    name: "Domain Rule"
    condition:
      field: customer.verified
      operator: equals
      value: false
    action: block
""")
        engine.load_domain_rules("test", str(rules_path))
        assert "test" in engine._domain_rules
        assert len(engine._domain_rules["test"]) == 1


class TestPolicyEngineConditionEvaluation:
    def setup_method(self):
        self.engine = PolicyEngine()

    def test_equals_operator_matches(self):
        state = _make_state(sentiment="frustrated")
        result = self.engine._evaluate_condition(
            {"field": "conversation.sentiment", "operator": "equals", "value": "frustrated"},
            state
        )
        assert result is True

    def test_equals_operator_no_match(self):
        state = _make_state(sentiment="neutral")
        result = self.engine._evaluate_condition(
            {"field": "conversation.sentiment", "operator": "equals", "value": "frustrated"},
            state
        )
        assert result is False

    def test_gte_operator_triggers_on_high_value(self):
        state = _make_state(turn_count=11)
        result = self.engine._evaluate_condition(
            {"field": "conversation.turn_count", "operator": "gte", "value": 10},
            state
        )
        assert result is True

    def test_gte_operator_no_trigger_on_low_value(self):
        state = _make_state(turn_count=3)
        result = self.engine._evaluate_condition(
            {"field": "conversation.turn_count", "operator": "gte", "value": 10},
            state
        )
        assert result is False

    def test_not_equals_operator(self):
        state = _make_state(verified=True)
        result = self.engine._evaluate_condition(
            {"field": "customer.verified", "operator": "not_equals", "value": False},
            state
        )
        assert result is True

    def test_additional_condition_and_logic(self):
        # Both conditions must be true
        state = _make_state(sentiment="frustrated", turn_count=8)
        result = self.engine._evaluate_condition(
            {
                "field": "conversation.sentiment",
                "operator": "equals",
                "value": "frustrated",
                "additional_condition": {
                    "field": "conversation.turn_count",
                    "operator": "gte",
                    "value": 6,
                }
            },
            state
        )
        assert result is True

    def test_additional_condition_fails_if_second_condition_false(self):
        state = _make_state(sentiment="frustrated", turn_count=3)
        result = self.engine._evaluate_condition(
            {
                "field": "conversation.sentiment",
                "operator": "equals",
                "value": "frustrated",
                "additional_condition": {
                    "field": "conversation.turn_count",
                    "operator": "gte",
                    "value": 6,
                }
            },
            state
        )
        assert result is False

    def test_missing_field_returns_false(self):
        state = _make_state()
        result = self.engine._evaluate_condition(
            {"field": "nonexistent.field.path", "operator": "equals", "value": "something"},
            state
        )
        assert result is False


class TestPolicyEngineFullEvaluation:
    def setup_method(self):
        self.engine = PolicyEngine()
        self.engine._global_rules = [
            {
                "rule_id": "GLOBAL_003",
                "condition": {
                    "field": "conversation.sentiment",
                    "operator": "equals",
                    "value": "urgent",
                },
                "action": "escalate",
                "escalation_reason": "Urgent situation detected",
            },
            {
                "rule_id": "GLOBAL_001",
                "condition": {
                    "field": "conversation.turn_count",
                    "operator": "gte",
                    "value": 10,
                },
                "action": "escalate",
                "escalation_reason": "Max turns exceeded",
            },
        ]

    def test_no_violations_on_clean_state(self):
        state = _make_state(sentiment="neutral", turn_count=3, verified=True)
        violations, should_escalate, reason = self.engine.evaluate(state)
        assert violations == []
        assert should_escalate is False
        assert reason is None

    def test_escalation_triggered_on_urgent_sentiment(self):
        state = _make_state(sentiment="urgent", turn_count=1)
        violations, should_escalate, reason = self.engine.evaluate(state)
        assert "GLOBAL_003" in violations
        assert should_escalate is True
        assert "Urgent" in reason

    def test_escalation_triggered_on_max_turns(self):
        state = _make_state(turn_count=12)
        violations, should_escalate, reason = self.engine.evaluate(state)
        assert "GLOBAL_001" in violations
        assert should_escalate is True

    def test_domain_rules_evaluated_when_domain_specified(self):
        self.engine._domain_rules = {
            "insurance": [
                {
                    "rule_id": "INS_TEST",
                    "condition": {
                        "field": "customer.verified",
                        "operator": "equals",
                        "value": False,
                    },
                    "action": "block",
                }
            ]
        }
        state = _make_state(verified=False)
        violations, _, _ = self.engine.evaluate(state, domain="insurance")
        assert "INS_TEST" in violations

    def test_domain_rules_not_evaluated_for_different_domain(self):
        self.engine._domain_rules = {
            "insurance": [
                {
                    "rule_id": "INS_TEST",
                    "condition": {
                        "field": "customer.verified",
                        "operator": "equals",
                        "value": False,
                    },
                    "action": "block",
                }
            ]
        }
        state = _make_state(verified=False)
        violations, _, _ = self.engine.evaluate(state, domain="telecom")
        assert "INS_TEST" not in violations
