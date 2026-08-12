from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

from app.tools.base import BaseTool


class LookupPremiumInput(BaseModel):
    policy_number: str


class PremiumDetails(BaseModel):
    policy_number: str
    annual_premium: float
    due_date: str
    outstanding_amount: float
    payment_status: Literal["paid", "due", "overdue", "grace_period"]
    ncb_percentage: int
    last_payment_date: Optional[str]
    last_payment_amount: Optional[float]


class ProcessPaymentInput(BaseModel):
    policy_number: str
    amount: float
    payment_method: Literal["upi", "credit_card", "debit_card", "net_banking", "cheque"]
    transaction_ref: Optional[str] = None


class PaymentResult(BaseModel):
    policy_number: str
    transaction_id: str
    amount: float
    payment_method: str
    status: Literal["success", "failed", "pending"]
    timestamp: str
    receipt_number: str
    next_due_date: Optional[str]


class RefundInput(BaseModel):
    policy_number: str
    amount: float
    reason: str


class RefundResult(BaseModel):
    policy_number: str
    refund_id: str
    amount: float
    reason: str
    status: Literal["initiated", "processing", "completed", "rejected"]
    estimated_credit_date: str
    timestamp: str


class LookupPremiumTool(BaseTool):
    """Look up premium details and payment status for a policy."""

    name = "lookup_premium"
    description = (
        "Retrieve premium amount, due date, payment status, and NCB details for a policy. "
        "Use before processing payment or when customer inquires about billing."
    )
    domains = ["insurance"]
    input_schema = LookupPremiumInput
    output_schema = PremiumDetails

    async def execute(self, input_data: LookupPremiumInput) -> PremiumDetails:
        # TODO: Replace with Billing System API call (SAP FICA / Policy Admin System)
        seed = hashlib.md5(input_data.policy_number.encode()).hexdigest()
        premium = round((int(seed[0:4], 16) % 40000 + 10000), -2)  # 10K-50K range
        ncb = [0, 20, 25, 35, 45, 50][int(seed[4], 16) % 6]
        status_list = ["paid", "due", "grace_period", "overdue"]
        status = status_list[int(seed[6], 16) % 4]

        last_payment = None
        if status == "paid":
            last_payment = "2024-01-15"

        return PremiumDetails(
            policy_number=input_data.policy_number,
            annual_premium=premium,
            due_date="2025-02-15",
            outstanding_amount=0.0 if status == "paid" else premium,
            payment_status=status,
            ncb_percentage=ncb,
            last_payment_date=last_payment,
            last_payment_amount=premium if last_payment else None,
        )


class ProcessPaymentTool(BaseTool):
    """Process an insurance premium payment."""

    name = "process_payment"
    description = (
        "Process a premium payment for an insurance policy. Supports UPI, cards, "
        "and net banking. Returns transaction ID and receipt."
    )
    domains = ["insurance"]
    input_schema = ProcessPaymentInput
    output_schema = PaymentResult

    async def execute(self, input_data: ProcessPaymentInput) -> PaymentResult:
        # TODO: Replace with Payment Gateway API call (Razorpay / PayU / CCAvenue / BillDesk)
        seed = hashlib.md5(f"{input_data.policy_number}{input_data.amount}".encode()).hexdigest()
        return PaymentResult(
            policy_number=input_data.policy_number,
            transaction_id=f"TXN-{seed[:8].upper()}",
            amount=input_data.amount,
            payment_method=input_data.payment_method,
            status="success",
            timestamp=datetime.utcnow().isoformat(),
            receipt_number=f"RCP-{seed[8:14].upper()}",
            next_due_date="2026-02-15",
        )


class InitiateRefundTool(BaseTool):
    """Initiate a refund for an insurance overpayment or policy cancellation."""

    name = "initiate_refund"
    description = (
        "Initiate a refund to the customer's original payment method. "
        "Used for policy cancellations or overpayment corrections."
    )
    domains = ["insurance"]
    input_schema = RefundInput
    output_schema = RefundResult

    async def execute(self, input_data: RefundInput) -> RefundResult:
        # TODO: Replace with Payment/Refund System API call
        seed = hashlib.md5(f"{input_data.policy_number}{input_data.amount}".encode()).hexdigest()
        return RefundResult(
            policy_number=input_data.policy_number,
            refund_id=f"RFD-{seed[:8].upper()}",
            amount=input_data.amount,
            reason=input_data.reason,
            status="initiated",
            estimated_credit_date="2024-02-01",
            timestamp=datetime.utcnow().isoformat(),
        )
