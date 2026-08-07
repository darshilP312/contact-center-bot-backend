"""
test_tools.py — Contract tests: verify every tool returns a valid ToolResult.
These run without any LLM calls or external services.
"""

import pytest
from app.tools.contracts import ToolResult
from app.tools import lookup_customer, check_outage, run_diagnostics
from app.tools import book_engineer, refund_payment, create_ticket


def assert_tool_result(result: dict) -> None:
    """Assert that a result conforms to the ToolResult contract."""
    assert isinstance(result, dict), "ToolResult must be a dict"
    assert "ok" in result, "ToolResult must have 'ok' key"
    assert "data" in result, "ToolResult must have 'data' key"
    assert "error" in result, "ToolResult must have 'error' key"
    assert isinstance(result["ok"], bool), "'ok' must be bool"
    assert isinstance(result["data"], dict), "'data' must be dict"
    if result["ok"]:
        assert result["error"] is None, "Successful result must have error=None"
    else:
        assert isinstance(result["error"], str), "Failed result must have error string"


class TestLookupCustomer:
    def test_known_account(self):
        result = lookup_customer.lookup_customer(account_no="ACC001")
        assert_tool_result(result)
        assert result["ok"] is True
        assert result["data"]["customer_id"] == "ACC001"
        assert result["data"]["verified"] is True
        assert result["data"]["tier"] == "premium"

    def test_known_phone(self):
        result = lookup_customer.lookup_customer(phone="+919123456789")
        assert_tool_result(result)
        assert result["ok"] is True
        assert result["data"]["customer_id"] == "ACC002"

    def test_unknown_returns_demo_fallback(self):
        result = lookup_customer.lookup_customer(account_no="UNKNOWN123")
        assert_tool_result(result)
        assert result["ok"] is True
        assert result["data"]["verified"] is True


class TestCheckOutage:
    def test_no_outage_area(self):
        result = check_outage.check_outage(area_code="DL110001")
        assert_tool_result(result)
        assert result["ok"] is True
        assert result["data"]["outage"] is False

    def test_outage_area(self):
        result = check_outage.check_outage(area_code="MH400002")
        assert_tool_result(result)
        assert result["ok"] is True
        assert result["data"]["outage"] is True
        assert "outage_id" in result["data"]

    def test_none_area_code(self):
        result = check_outage.check_outage(area_code=None)
        assert_tool_result(result)
        assert result["ok"] is True


class TestRunDiagnostics:
    def test_returns_valid_contract(self):
        result = run_diagnostics.run_diagnostics(customer_id="ACC001")
        assert_tool_result(result)
        assert result["ok"] is True
        assert "diagnostic_passed" in result["data"]
        assert "signal_strength" in result["data"]


class TestBookEngineer:
    def test_standard_booking(self):
        result = book_engineer.book_engineer(customer_id="ACC001")
        assert_tool_result(result)
        assert result["ok"] is True
        assert result["data"]["engineer_booked"] is True
        assert "booking_ref" in result["data"]
        assert result["data"]["booking_ref"].startswith("ENG-")

    def test_high_priority(self):
        result = book_engineer.book_engineer(priority="high", reason="3 diagnostics failed")
        assert_tool_result(result)
        assert result["ok"] is True


class TestRefundPayment:
    def test_valid_refund(self):
        result = refund_payment.refund_payment(amount=2500, customer_id="ACC001")
        assert_tool_result(result)
        assert result["ok"] is True
        assert result["data"]["refund_triggered"] is True
        assert result["data"]["refund_ref"].startswith("REF-")

    def test_zero_amount_fails(self):
        result = refund_payment.refund_payment(amount=0)
        assert_tool_result(result)
        assert result["ok"] is False

    def test_over_limit_fails(self):
        result = refund_payment.refund_payment(amount=15000)
        assert_tool_result(result)
        assert result["ok"] is False


class TestCreateTicket:
    def test_creates_ticket(self):
        result = create_ticket.create_ticket(customer_id="ACC001", session_id="test")
        assert_tool_result(result)
        assert result["ok"] is True
        assert result["data"]["ticket_created"] is True
        ticket_id = result["data"]["ticket_id"]
        assert ticket_id.startswith("INC-") or ticket_id.startswith("REQ-")

    def test_request_type(self):
        result = create_ticket.create_ticket(ticket_type="request")
        assert_tool_result(result)
        assert result["data"]["ticket_id"].startswith("REQ-")
