"""
test_workflows.py — Workflow loader and executor tests.
Verify YAML loading, step transitions, and flag updates.
"""

import pytest
from app.workflows.loader import load_workflow, list_workflows
from app.workflows.executor import advance_workflow, get_step_goal


class TestWorkflowLoader:
    def test_load_technical_support(self):
        wf = load_workflow("technical_support")
        assert wf.name == "technical_support"
        assert wf.entry_step == "authenticate"
        assert "authenticate" in wf.steps
        assert "run_diagnostics" in wf.steps
        assert "book_engineer" in wf.steps

    def test_load_billing_refund(self):
        wf = load_workflow("billing_refund")
        assert wf.name == "billing_refund"
        assert wf.entry_step == "authenticate"

    def test_load_policy_rag(self):
        wf = load_workflow("policy_rag")
        assert wf.name == "policy_rag"

    def test_step_transitions_defined(self):
        wf = load_workflow("technical_support")
        auth_step = wf.get_step("authenticate")
        assert auth_step.on_success == "check_outage"
        assert auth_step.on_fail == "escalate"

    def test_unknown_workflow_raises(self):
        with pytest.raises(FileNotFoundError):
            load_workflow("nonexistent_workflow")

    def test_list_workflows(self):
        workflows = list_workflows()
        assert "technical_support" in workflows
        assert "billing_refund" in workflows
        assert "policy_rag" in workflows


class TestWorkflowExecutor:
    def base_state(self) -> dict:
        return {
            "workflow": {
                "name": "technical_support",
                "step": "authenticate",
                "completed_steps": [],
                "step_attempts": {},
                "step_results": {},
            },
            "flags": {
                "ticket_created": False,
                "engineer_booked": False,
                "escalated": False,
                "awaiting_approval": False,
                "refund_triggered": False,
                "rag_used": False,
                "barge_in_detected": False,
            },
            "customer": {},
            "ticket_id": None,
        }

    def test_successful_auth_advances_to_check_outage(self):
        state = self.base_state()
        tool_result = {"ok": True, "data": {"verified": True}, "error": None}
        updated = advance_workflow(state, tool_result)
        assert updated["workflow"]["step"] == "check_outage"
        assert "authenticate" in updated["workflow"]["completed_steps"]

    def test_failed_auth_advances_to_escalate(self):
        state = self.base_state()
        tool_result = {"ok": False, "data": {}, "error": "Not found"}
        updated = advance_workflow(state, tool_result)
        assert updated["workflow"]["step"] == "escalate"

    def test_ticket_flag_set_on_ticket_creation(self):
        state = self.base_state()
        state["workflow"]["step"] = "create_ticket"
        tool_result = {
            "ok": True,
            "data": {"ticket_id": "INC-12345", "ticket_created": True},
            "error": None,
        }
        updated = advance_workflow(state, tool_result)
        assert updated["flags"]["ticket_created"] is True
        assert updated["ticket_id"] == "INC-12345"

    def test_engineer_flag_set(self):
        state = self.base_state()
        state["workflow"]["step"] = "book_engineer"
        tool_result = {
            "ok": True,
            "data": {"engineer_booked": True, "booking_ref": "ENG-ABC"},
            "error": None,
        }
        updated = advance_workflow(state, tool_result)
        assert updated["flags"]["engineer_booked"] is True

    def test_outage_branch(self):
        state = self.base_state()
        state["workflow"]["step"] = "check_outage"
        # outage_found=True should trigger the branch
        tool_result = {
            "ok": True,
            "data": {"outage": True, "outage_found": True},
            "error": None,
        }
        updated = advance_workflow(state, tool_result)
        assert updated["workflow"]["step"] == "create_ticket_outage"
