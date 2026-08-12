"""
book_engineer.py — Mock scheduling: book a field engineer visit.
Returns appointment details with a generated booking reference.
"""

import uuid
from datetime import datetime, timedelta
from app.tools.contracts import ToolResult, ok_result, err_result


def book_engineer(
    customer_id: str = None,
    reason: str = "Technical issue",
    priority: str = "standard",
    session_id: str = None,
    **kwargs,
) -> ToolResult:
    """
    Schedule a field technician visit for the next available slot.
    Priority 'high' books same-day if before 14:00, else next morning.
    """
    now = datetime.now()
    if priority == "high" and now.hour < 14:
        slot = now.replace(hour=16, minute=0, second=0, microsecond=0)
    else:
        slot = (now + timedelta(days=1)).replace(
            hour=10, minute=0, second=0, microsecond=0
        )

    booking_ref = f"ENG-{uuid.uuid4().hex[:6].upper()}"

    return ok_result({
        "booking_ref": booking_ref,
        "engineer_booked": True,
        "appointment_datetime": slot.isoformat(),
        "appointment_display": slot.strftime("%A, %d %B at %I:%M %p"),
        "priority": priority,
        "reason": reason,
        "technician_name": "Raj Kumar",
        "technician_contact": "+91-9000000001",
    })
