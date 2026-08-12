"""
create_ticket.py — Mock ticketing: create an incident/service ticket.
Returns a ticket ID that is displayed in the UI and referenced in the response.
"""

import uuid
import random
from datetime import datetime, timezone
from app.tools.contracts import ToolResult, ok_result


def create_ticket(
    customer_id: str = None,
    session_id: str = None,
    intent: str = "general",
    summary: str = "",
    priority: str = "medium",
    ticket_type: str = "incident",
    **kwargs,
) -> ToolResult:
    """
    Create a support ticket and return the ticket ID.
    Ticket ID format: INC-XXXXX (for incidents), REQ-XXXXX (for requests).
    """
    prefix = "REQ" if ticket_type == "request" else "INC"
    ticket_id = f"{prefix}-{random.randint(10000, 99999)}"

    sla_hours_map = {"critical": 2, "high": 4, "medium": 24, "low": 72}
    sla_hours = sla_hours_map.get(priority, 24)

    return ok_result({
        "ticket_id": ticket_id,
        "ticket_created": True,
        "ticket_type": ticket_type,
        "priority": priority,
        "intent": intent,
        "summary": summary or f"Auto-created for session {session_id}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sla_hours": sla_hours,
        "status": "open",
        "message": f"Ticket {ticket_id} created with {priority} priority.",
    })
