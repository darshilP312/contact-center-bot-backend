from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.core.logging import get_logger

logger = get_logger("policies.engine")


class PolicyEngine:
    """
    Policy evaluator loading global + domain-specific rules from YAML.

    Rule evaluation is declarative — rules are defined in YAML, not Python.
    This means new policy rules require only YAML changes, not code changes.

    Evaluation order:
    1. Global rules (policies/global_rules.yaml) — includes Decision Engine rules DE-001/002/003
    2. Domain-specific rules (domains/{domain}/policies/rules.yaml)

    Supported condition operators:
    - equals, not_equals
    - gte (>=), lte (<=)
    - length_gte (len(actual) >= value)
    - contains (value in actual list)
    - contains_any (actual matches any item in value list)
    - is_null, not_null

    All conditions support AND chaining via `additional_condition` key.
    """

    def __init__(self) -> None:
        self._global_rules: list[dict] = []
        self._domain_rules: dict[str, list[dict]] = {}

    def load_global_rules(self) -> None:
        """Load global rules from the global_rules.yaml file."""
        global_rules_path = Path(__file__).parent / "global_rules.yaml"
        if global_rules_path.exists():
            with open(global_rules_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            self._global_rules = config.get("rules", [])
            logger.info(
                "Global policy rules loaded",
                node="policies.engine",
                rule_count=len(self._global_rules),
            )

    def load_domain_rules(self, domain_id: str, rules_yaml_path: str) -> None:
        """Load domain-specific rules from a YAML file."""
        path = Path(rules_yaml_path)
        if path.exists():
            with open(path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            self._domain_rules[domain_id] = config.get("rules", [])
            logger.info(
                "Domain policy rules loaded",
                node="policies.engine",
                domain_id=domain_id,
                rule_count=len(self._domain_rules[domain_id]),
            )

    def _get_value(self, state: dict[str, Any], field_path: str) -> Any:
        """Navigate dot-notation path to get a value from AgentState."""
        parts = field_path.split(".")
        current = state
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return None
        return current

    def _evaluate_condition(self, condition: dict, state: dict[str, Any]) -> bool:
        """
        Evaluate a single rule condition against the current AgentState.

        Supported operators:
        - equals / not_equals
        - gte / lte (numeric comparison)
        - length_gte (collection length)
        - contains (value IN actual collection)
        - contains_any (actual matches ANY item in value list)
        - is_null / not_null
        """
        field = condition.get("field", "")
        operator = condition.get("operator", "equals")
        expected = condition.get("value")
        actual = self._get_value(state, field)

        result = False

        if operator == "equals":
            result = actual == expected

        elif operator == "not_equals":
            result = actual != expected

        elif operator == "gte":
            try:
                result = float(actual or 0) >= float(expected)
            except (TypeError, ValueError):
                result = False

        elif operator == "lte":
            try:
                result = float(actual or 0) <= float(expected)
            except (TypeError, ValueError):
                result = False

        elif operator == "length_gte":
            try:
                result = len(actual or []) >= int(expected)
            except (TypeError, ValueError):
                result = False

        elif operator == "contains":
            # expected IN actual (e.g., "angry" in ["angry", "frustrated"])
            result = expected in (actual or [])

        elif operator == "contains_any":
            # actual matches ANY item from the expected list
            # e.g., actual="angry", expected=["angry", "frustrated"] → True
            expected_list = expected if isinstance(expected, list) else [expected]
            result = actual in expected_list

        elif operator == "is_null":
            result = actual is None

        elif operator == "not_null":
            result = actual is not None

        # AND chain via additional_condition
        if result and "additional_condition" in condition:
            result = self._evaluate_condition(condition["additional_condition"], state)

        return result

    def evaluate(
        self, state: dict[str, Any], domain: str | None = None
    ) -> tuple[list[str], bool, str | None, list[dict]]:
        """
        Evaluate all applicable policy rules against the current AgentState.

        Args:
            state: The full AgentState dict.
            domain: Active domain ID for loading domain-specific rules.

        Returns:
            Tuple of:
            - violations: List of triggered rule IDs
            - should_escalate: Whether any rule triggered escalation
            - escalation_reason: The reason for escalation if applicable
            - policy_evaluations: Structured audit log for each rule checked
              (matches Decision Engine output schema)
        """
        violations: list[str] = []
        should_escalate = False
        escalation_reason: str | None = None
        policy_evaluations: list[dict] = []

        all_rules = list(self._global_rules)
        if domain and domain in self._domain_rules:
            all_rules.extend(self._domain_rules[domain])

        for rule in all_rules:
            condition = rule.get("condition", {})
            if not condition:
                continue

            triggered = self._evaluate_condition(condition, state)
            rule_id = rule.get("rule_id", "UNKNOWN")
            action = rule.get("action", "flag")

            # Build evaluation entry (matches planner output schema)
            evaluation_entry: dict = {
                "rule_checked": f"{rule_id}: {rule.get('name', '')}",
                "passed": not triggered,          # "passed" = rule did NOT trigger
                "action_taken": "proceed" if not triggered else action,
            }

            if triggered:
                violations.append(rule_id)
                evaluation_entry["action_taken"] = action

                if action == "escalate":
                    should_escalate = True
                    escalation_reason = rule.get(
                        "escalation_reason", "Policy rule triggered escalation"
                    )
                    evaluation_entry["escalation_reason"] = escalation_reason

                elif action == "request_approval":
                    evaluation_entry["approval_reason"] = rule.get("approval_reason", "")
                    evaluation_entry["redirect_tool"] = rule.get("redirect_tool", "")

                logger.info(
                    "Policy rule triggered",
                    node="policies.engine",
                    rule_id=rule_id,
                    action=action,
                    domain=domain,
                )
            else:
                evaluation_entry["action_taken"] = "proceed"

            policy_evaluations.append(evaluation_entry)

        return violations, should_escalate, escalation_reason, policy_evaluations

    def evaluate_hard_rules(
        self, state: dict[str, Any]
    ) -> tuple[bool, str | None, str | None]:
        """
        Evaluate ONLY the three Decision Engine hard rules synchronously.

        This is called by the guardrails node for fast pre-LLM checks
        without loading all YAML rules. Returns lightweight results.

        Args:
            state: The full AgentState.

        Returns:
            Tuple of:
            - triggered: Whether any hard rule fired
            - rule_id: The rule that fired (DE-001 / DE-002 / DE-003)
            - action: "escalate" | "request_approval" | None
        """
        conversation = state.get("conversation")
        sentiment = conversation.sentiment if conversation else "neutral"
        turn_count = conversation.turn_count if conversation else 0
        failed_diag = state.get("failed_diagnostics_count", 0)
        refund_amount = state.get("refund_amount")

        # DE-001: Angry/frustrated sentiment with ≥6 turns
        if (sentiment == "angry" and turn_count >= 6) or (sentiment == "frustrated" and turn_count >= 8):
            return True, "DE-001", "escalate"

        # DE-003: Diagnostic failure limit
        if failed_diag >= 3:
            return True, "DE-003", "escalate"

        # DE-002: Refund monetary gate
        if refund_amount is not None and refund_amount >= 10_000.0:
            return True, "DE-002", "request_approval"

        return False, None, None
