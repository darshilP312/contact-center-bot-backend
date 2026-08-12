from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Literal, Optional

from pydantic import BaseModel

from app.tools.base import BaseTool


class BookSurveyorInput(BaseModel):
    claim_id: str
    preferred_date: str
    location: str
    contact_phone: Optional[str] = None


class BookingConfirmation(BaseModel):
    claim_id: str
    booking_id: str
    surveyor_name: str
    surveyor_phone: str
    confirmed_date: str
    confirmed_time: str
    location: str
    status: Literal["confirmed", "pending", "rescheduled"]
    notes: str


class ScheduleInspectionInput(BaseModel):
    policy_number: str
    inspection_type: Literal["pre_renewal", "risk_assessment", "reinstatement"]
    preferred_date: Optional[str] = None


class InspectionSchedule(BaseModel):
    policy_number: str
    inspection_id: str
    inspection_type: str
    inspector_name: str
    scheduled_date: str
    scheduled_time: str
    status: str
    notes: str


class BookSurveyorTool(BaseTool):
    """Book a surveyor visit for claim damage assessment."""

    name = "book_surveyor"
    description = (
        "Schedule a surveyor to visit the customer's location to assess insurance "
        "claim damage. Takes preferred date and location, confirms booking."
    )
    domains = ["insurance"]
    input_schema = BookSurveyorInput
    output_schema = BookingConfirmation

    async def execute(self, input_data: BookSurveyorInput) -> BookingConfirmation:
        # TODO: Replace with Surveyor Scheduling System API (internal field service management)
        seed = hashlib.md5(f"{input_data.claim_id}{input_data.preferred_date}".encode()).hexdigest()
        surveyors = [
            ("Rajesh Kumar", "+91-98765-43210"),
            ("Sunita Verma", "+91-87654-32109"),
            ("Arun Nair", "+91-76543-21098"),
            ("Meena Joshi", "+91-65432-10987"),
        ]
        idx = int(seed[0], 16) % len(surveyors)
        name, phone = surveyors[idx]

        # Confirm date or shift by 1 day if weekend
        try:
            pref_date = datetime.strptime(input_data.preferred_date, "%Y-%m-%d")
        except ValueError:
            pref_date = datetime.utcnow() + timedelta(days=3)

        if pref_date.weekday() >= 5:  # Weekend
            pref_date += timedelta(days=2)

        time_slots = ["09:00 AM", "11:00 AM", "02:00 PM", "04:00 PM"]
        time_slot = time_slots[int(seed[2], 16) % len(time_slots)]

        return BookingConfirmation(
            claim_id=input_data.claim_id,
            booking_id=f"BKG-{seed[:6].upper()}",
            surveyor_name=name,
            surveyor_phone=phone,
            confirmed_date=pref_date.strftime("%Y-%m-%d"),
            confirmed_time=time_slot,
            location=input_data.location,
            status="confirmed",
            notes=(
                f"Surveyor {name} will visit on {pref_date.strftime('%d %B %Y')} at {time_slot}. "
                f"Please ensure the vehicle/property is accessible. Contact: {phone}"
            ),
        )


class ScheduleInspectionTool(BaseTool):
    """Schedule a pre-renewal or risk assessment inspection."""

    name = "schedule_inspection"
    description = (
        "Schedule a pre-renewal vehicle/property inspection or risk assessment. "
        "Required for policies older than 3 years or after reinstatement."
    )
    domains = ["insurance"]
    input_schema = ScheduleInspectionInput
    output_schema = InspectionSchedule

    async def execute(self, input_data: ScheduleInspectionInput) -> InspectionSchedule:
        # TODO: Replace with Inspection Management System API
        seed = hashlib.md5(f"{input_data.policy_number}{input_data.inspection_type}".encode()).hexdigest()
        inspectors = ["Vikram Singh", "Lakshmi Rao", "Deepak Mehta"]
        idx = int(seed[0], 16) % len(inspectors)

        scheduled = datetime.utcnow() + timedelta(days=int(seed[2], 16) % 7 + 3)

        return InspectionSchedule(
            policy_number=input_data.policy_number,
            inspection_id=f"INS-{seed[:6].upper()}",
            inspection_type=input_data.inspection_type,
            inspector_name=inspectors[idx],
            scheduled_date=scheduled.strftime("%Y-%m-%d"),
            scheduled_time="10:00 AM",
            status="scheduled",
            notes=f"Inspection scheduled for {input_data.inspection_type.replace('_', ' ')}. Inspector will call 30 minutes before arrival.",
        )
