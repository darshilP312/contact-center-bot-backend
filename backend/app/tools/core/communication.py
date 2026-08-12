from __future__ import annotations

import hashlib
from datetime import datetime

from pydantic import BaseModel

from app.tools.base import BaseTool


class SendSMSInput(BaseModel):
    customer_id: str
    message: str
    phone: str | None = None


class SMSResult(BaseModel):
    customer_id: str
    message_id: str
    status: str
    sent_at: str


class SendEmailInput(BaseModel):
    customer_id: str
    subject: str
    body: str
    email: str | None = None


class EmailResult(BaseModel):
    customer_id: str
    message_id: str
    subject: str
    status: str
    sent_at: str


class SendSMSTool(BaseTool):
    """Send an SMS notification to a customer."""

    name = "send_sms"
    description = (
        "Send an SMS message to a customer. Use for confirmations, OTPs, "
        "claim reference numbers, and payment receipts."
    )
    domains = ["*"]
    input_schema = SendSMSInput
    output_schema = SMSResult

    async def execute(self, input_data: SendSMSInput) -> SMSResult:
        # TODO: Replace with SMS gateway API call (Twilio / AWS SNS / Kaleyra / MSG91)
        seed = hashlib.md5(f"{input_data.customer_id}{input_data.message[:10]}".encode()).hexdigest()
        return SMSResult(
            customer_id=input_data.customer_id,
            message_id=f"MSG-{seed[:8].upper()}",
            status="sent",
            sent_at=datetime.utcnow().isoformat(),
        )


class SendEmailTool(BaseTool):
    """Send an email notification to a customer."""

    name = "send_email"
    description = (
        "Send an email to a customer with a subject and body. Use for policy documents, "
        "claim summaries, renewal notices, and detailed confirmations."
    )
    domains = ["*"]
    input_schema = SendEmailInput
    output_schema = EmailResult

    async def execute(self, input_data: SendEmailInput) -> EmailResult:
        # TODO: Replace with email service API call (AWS SES / SendGrid / Mailgun)
        seed = hashlib.md5(f"{input_data.customer_id}{input_data.subject}".encode()).hexdigest()
        return EmailResult(
            customer_id=input_data.customer_id,
            message_id=f"EMAIL-{seed[:8].upper()}",
            subject=input_data.subject,
            status="sent",
            sent_at=datetime.utcnow().isoformat(),
        )
