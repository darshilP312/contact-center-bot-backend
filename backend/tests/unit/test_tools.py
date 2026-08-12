"""Unit tests for all tool implementations."""
from __future__ import annotations

import pytest

from app.tools.core.crm import LookupCustomerTool, LookupCustomerInput, VerifyCustomerTool, VerifyCustomerInput
from app.tools.core.communication import SendSMSTool, SendSMSInput, SendEmailTool, SendEmailInput
from app.tools.core.ticketing import CreateTicketTool, CreateTicketInput
from app.tools.core.handoff import RouteToHumanAgentTool, RouteToHumanInput
from app.tools.insurance.policy import LookupPolicyTool, LookupPolicyInput
from app.tools.insurance.claims import FileClaimTool, FileClaimInput, CheckClaimStatusTool, CheckClaimInput
from app.tools.insurance.billing import LookupPremiumTool, LookupPremiumInput, ProcessPaymentTool, ProcessPaymentInput
from app.tools.insurance.scheduling import BookSurveyorTool, BookSurveyorInput


class TestCRMTools:
    @pytest.mark.asyncio
    async def test_lookup_customer_returns_profile(self):
        tool = LookupCustomerTool()
        result = await tool.execute(LookupCustomerInput(customer_id="CUST-001"))
        assert result.customer_id == "CUST-001"
        assert result.name
        assert result.tier in ("standard", "premium", "enterprise")
        assert result.email.endswith("@email.example.com")

    @pytest.mark.asyncio
    async def test_lookup_customer_is_deterministic(self):
        tool = LookupCustomerTool()
        r1 = await tool.execute(LookupCustomerInput(customer_id="CUST-ABC"))
        r2 = await tool.execute(LookupCustomerInput(customer_id="CUST-ABC"))
        assert r1.name == r2.name
        assert r1.tier == r2.tier

    @pytest.mark.asyncio
    async def test_lookup_customer_different_inputs_differ(self):
        tool = LookupCustomerTool()
        r1 = await tool.execute(LookupCustomerInput(customer_id="CUST-001"))
        r2 = await tool.execute(LookupCustomerInput(customer_id="CUST-999"))
        # Different IDs should produce deterministically different output
        # (not guaranteed to differ on every field, but account_no should differ)
        assert r1.account_no != r2.account_no or r1.name != r2.name

    @pytest.mark.asyncio
    async def test_verify_customer_valid_input(self):
        tool = VerifyCustomerTool()
        result = await tool.execute(VerifyCustomerInput(
            customer_id="CUST-001",
            dob="1990-01-15",
            last_4_account="1234",
        ))
        assert isinstance(result.verified, bool)
        assert result.customer_id == "CUST-001"

    @pytest.mark.asyncio
    async def test_verify_customer_invalid_dob_fails(self):
        tool = VerifyCustomerTool()
        result = await tool.execute(VerifyCustomerInput(
            customer_id="CUST-001",
            dob="invalid",
            last_4_account="1234",
        ))
        assert result.verified is False


class TestCommunicationTools:
    @pytest.mark.asyncio
    async def test_send_sms_returns_message_id(self):
        tool = SendSMSTool()
        result = await tool.execute(SendSMSInput(customer_id="CUST-001", message="Test message"))
        assert result.message_id.startswith("MSG-")
        assert result.status == "sent"

    @pytest.mark.asyncio
    async def test_send_email_returns_message_id(self):
        tool = SendEmailTool()
        result = await tool.execute(SendEmailInput(
            customer_id="CUST-001", subject="Test", body="Test body"
        ))
        assert result.message_id.startswith("EMAIL-")
        assert result.status == "sent"


class TestTicketingTools:
    @pytest.mark.asyncio
    async def test_create_ticket_returns_ticket_id(self):
        tool = CreateTicketTool()
        result = await tool.execute(CreateTicketInput(
            session_id="sess_test",
            customer_id="CUST-001",
            intent="file_claim",
            description="Car accident claim",
            priority="high",
        ))
        assert result.ticket_id.startswith("TKT-")
        assert result.status == "open"
        assert result.priority == "high"


class TestHandoffTools:
    @pytest.mark.asyncio
    async def test_route_to_human_returns_handoff(self):
        tool = RouteToHumanAgentTool()
        result = await tool.execute(RouteToHumanInput(
            session_id="sess_test",
            escalation_reason="Customer frustrated",
            final_sentiment="frustrated",
            transcript_summary="Customer called about a claim.",
        ))
        assert result.handoff_id.startswith("HND-")
        assert result.status == "queued"
        assert result.queue_position >= 1


class TestInsurancePolicyTools:
    @pytest.mark.asyncio
    async def test_lookup_policy_returns_details(self):
        tool = LookupPolicyTool()
        result = await tool.execute(LookupPolicyInput(policy_number="POL-123456"))
        assert result.policy_number == "POL-123456"
        assert result.status in ("active", "expired", "cancelled", "suspended")
        assert result.idv > 0
        assert result.premium_annual > 0

    @pytest.mark.asyncio
    async def test_lookup_policy_is_deterministic(self):
        tool = LookupPolicyTool()
        r1 = await tool.execute(LookupPolicyInput(policy_number="POL-ABC"))
        r2 = await tool.execute(LookupPolicyInput(policy_number="POL-ABC"))
        assert r1.idv == r2.idv
        assert r1.premium_annual == r2.premium_annual


class TestInsuranceClaimsTools:
    @pytest.mark.asyncio
    async def test_file_claim_returns_claim_id(self):
        tool = FileClaimTool()
        result = await tool.execute(FileClaimInput(
            policy_number="POL-123",
            incident_date="2024-01-15",
            incident_type="car_accident",
            damage_amount=50000.0,
            description="Front-end collision",
        ))
        assert result.claim_id.startswith("CLM-")
        assert result.status == "registered"
        assert result.expected_settlement > 0

    @pytest.mark.asyncio
    async def test_file_claim_large_requires_surveyor(self):
        tool = FileClaimTool()
        result = await tool.execute(FileClaimInput(
            policy_number="POL-123",
            incident_date="2024-01-15",
            incident_type="car_accident",
            damage_amount=150000.0,
            description="Major collision",
        ))
        assert result.surveyor_required is True

    @pytest.mark.asyncio
    async def test_check_claim_status_returns_status(self):
        tool = CheckClaimStatusTool()
        result = await tool.execute(CheckClaimInput(claim_id="CLM-ABC123"))
        assert result.claim_id == "CLM-ABC123"
        assert result.status in ("registered", "under_review", "surveyor_assigned", "approved", "payment_processing")


class TestInsuranceBillingTools:
    @pytest.mark.asyncio
    async def test_lookup_premium_returns_details(self):
        tool = LookupPremiumTool()
        result = await tool.execute(LookupPremiumInput(policy_number="POL-123"))
        assert result.annual_premium > 0
        assert result.payment_status in ("paid", "due", "overdue", "grace_period")
        assert 0 <= result.ncb_percentage <= 50

    @pytest.mark.asyncio
    async def test_process_payment_returns_success(self):
        tool = ProcessPaymentTool()
        result = await tool.execute(ProcessPaymentInput(
            policy_number="POL-123",
            amount=15000.0,
            payment_method="upi",
        ))
        assert result.transaction_id.startswith("TXN-")
        assert result.status == "success"
        assert result.receipt_number.startswith("RCP-")


class TestInsuranceSchedulingTools:
    @pytest.mark.asyncio
    async def test_book_surveyor_returns_confirmation(self):
        tool = BookSurveyorTool()
        result = await tool.execute(BookSurveyorInput(
            claim_id="CLM-123",
            preferred_date="2024-02-05",
            location="Mumbai, Maharashtra",
        ))
        assert result.booking_id.startswith("BKG-")
        assert result.status == "confirmed"
        assert result.surveyor_name
        assert result.confirmed_time


class TestToolDomainScoping:
    def test_core_tool_available_to_all_domains(self):
        tool = LookupCustomerTool()
        assert "*" in tool.domains

    def test_insurance_tool_scoped_to_insurance(self):
        tool = LookupPolicyTool()
        assert "insurance" in tool.domains
        assert "*" not in tool.domains

    def test_tool_name_is_snake_case(self):
        tools = [
            LookupCustomerTool(), VerifyCustomerTool(),
            SendSMSTool(), SendEmailTool(),
            LookupPolicyTool(), FileClaimTool(),
        ]
        for tool in tools:
            assert tool.name == tool.name.lower()
            assert " " not in tool.name
