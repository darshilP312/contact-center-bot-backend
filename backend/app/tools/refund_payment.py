"""
refund_payment.py — Mock billing: process a customer refund.
NOTE: Amounts > Rs.10,000 are BLOCKED by the policy engine BEFORE this is called.
This tool is the final execution step after policy approval.
"""

import uuid
from app.tools.contracts import ToolResult, ok_result, err_result


def refund_payment(
    customer_id: str = None,
    amount: float = 0,
    reason: str = "Customer request",
    invoice_id: str = None,
    session_id: str = None,
    **kwargs,
) -> ToolResult:
    """
    Process a payment refund for the customer.
    The policy engine guarantees this is only called for amounts <= Rs.10,000.
    """
    if not amount or amount <= 0:
        return err_result("Refund amount must be greater than 0.")

    # Belt-and-suspenders: catch the case where policy engine failed to block
    if amount > 10_000:
        return err_result(
            "Refund amount exceeds policy limit of Rs.10,000. Manager approval required."
        )

    refund_ref = f"REF-{uuid.uuid4().hex[:8].upper()}"

    return ok_result({
        "refund_ref": refund_ref,
        "refund_triggered": True,
        "amount": amount,
        "currency": "INR",
        "formatted_amount": f"Rs.{amount:,.2f}",
        "reason": reason,
        "invoice_id": invoice_id,
        "processing_days": 3,
        "message": (
            f"Refund of Rs.{amount:,.2f} initiated. "
            f"Reference: {refund_ref}. "
            f"You will see this in your account within 3 business days."
        ),
    })
