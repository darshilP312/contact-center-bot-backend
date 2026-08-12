from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

from app.tools.base import BaseTool


class CreateTicketInput(BaseModel):
    session_id: str
    customer_id: str
    intent: str
    description: str
    priority: Literal["low", "medium", "high", "critical"] = "medium"


class Ticket(BaseModel):
    ticket_id: str
    session_id: str
    customer_id: str
    intent: str
    description: str
    priority: str
    status: str
    created_at: str
    updated_at: str


class UpdateTicketInput(BaseModel):
    ticket_id: str
    update: str
    status: Optional[str] = None


class GetTicketInput(BaseModel):
    ticket_id: str


class CreateTicketTool(BaseTool):
    """Create a support ticket for this session."""

    name = "create_ticket"
    description = (
        "Create a support ticket to log customer interaction, claim, or complaint. "
        "Returns a ticket ID for future reference and tracking."
    )
    domains = ["*"]
    input_schema = CreateTicketInput
    output_schema = Ticket

    async def execute(self, input_data: CreateTicketInput) -> Ticket:
        # TODO: Replace with ticketing system API call (Zendesk / Freshdesk / ServiceNow / Jira SD)
        seed = hashlib.md5(f"{input_data.session_id}{input_data.intent}".encode()).hexdigest()
        now = datetime.utcnow().isoformat()
        return Ticket(
            ticket_id=f"TKT-{seed[:6].upper()}",
            session_id=input_data.session_id,
            customer_id=input_data.customer_id,
            intent=input_data.intent,
            description=input_data.description,
            priority=input_data.priority,
            status="open",
            created_at=now,
            updated_at=now,
        )


class UpdateTicketTool(BaseTool):
    """Update an existing support ticket with new information."""

    name = "update_ticket"
    description = "Update the status or add notes to an existing support ticket."
    domains = ["*"]
    input_schema = UpdateTicketInput
    output_schema = Ticket

    async def execute(self, input_data: UpdateTicketInput) -> Ticket:
        # TODO: Replace with ticketing system PATCH API call
        seed = hashlib.md5(input_data.ticket_id.encode()).hexdigest()
        now = datetime.utcnow().isoformat()
        return Ticket(
            ticket_id=input_data.ticket_id,
            session_id="sess_mock",
            customer_id=f"CUST-{seed[:6].upper()}",
            intent="general",
            description=input_data.update,
            priority="medium",
            status=input_data.status or "in_progress",
            created_at=now,
            updated_at=now,
        )


class GetTicketTool(BaseTool):
    """Retrieve a support ticket by ID."""

    name = "get_ticket"
    description = "Retrieve details of an existing support ticket by its ticket ID."
    domains = ["*"]
    input_schema = GetTicketInput
    output_schema = Ticket

    async def execute(self, input_data: GetTicketInput) -> Ticket:
        # TODO: Replace with ticketing system GET API call
        seed = hashlib.md5(input_data.ticket_id.encode()).hexdigest()
        return Ticket(
            ticket_id=input_data.ticket_id,
            session_id="sess_mock",
            customer_id=f"CUST-{seed[:6].upper()}",
            intent="general",
            description="Support ticket for customer inquiry",
            priority="medium",
            status="open",
            created_at="2024-01-20T10:00:00",
            updated_at="2024-01-20T10:00:00",
        )
