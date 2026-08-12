from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Literal, Optional

from pydantic import BaseModel

from app.tools.base import BaseTool


class FileClaimInput(BaseModel):
    policy_number: str
    incident_date: str
    incident_type: str
    damage_amount: float
    description: str
    location: Optional[str] = None
    third_party_involved: bool = False


class ClaimResult(BaseModel):
    claim_id: str
    policy_number: str
    status: Literal["registered", "under_review", "approved", "rejected", "closed"]
    incident_type: str
    damage_amount: float
    expected_settlement: float
    surveyor_required: bool
    registered_at: str
    estimated_settlement_date: str
    notes: str


class CheckClaimInput(BaseModel):
    claim_id: str


class ClaimStatus(BaseModel):
    claim_id: str
    policy_number: str
    status: str
    stage: str
    damage_amount: float
    approved_amount: Optional[float]
    surveyor_name: Optional[str]
    surveyor_visit_date: Optional[str]
    last_updated: str
    next_action: str


class AssignSurveyorInput(BaseModel):
    claim_id: str


class SurveyorAssignment(BaseModel):
    claim_id: str
    surveyor_id: str
    surveyor_name: str
    surveyor_phone: str
    assigned_at: str
    expected_visit_date: str


class FileClaimTool(BaseTool):
    """File a new insurance claim and receive a claim reference ID."""

    name = "file_claim"
    description = (
        "File a new insurance claim for an incident. Requires policy number, "
        "incident date, type, and damage estimate. Returns a claim ID."
    )
    domains = ["insurance"]
    input_schema = FileClaimInput
    output_schema = ClaimResult

    async def execute(self, input_data: FileClaimInput) -> ClaimResult:
        # TODO: Replace with Claims Management System API call (Guidewire / ClaimCenter / Duck Creek)
        seed = hashlib.md5(f"{input_data.policy_number}{input_data.incident_date}".encode()).hexdigest()
        claim_id = f"CLM-{seed[:6].upper()}"
        now = datetime.utcnow()
        settlement_days = 7 if input_data.damage_amount < 50000 else 15

        # Surveyor required for damage > ₹10,000
        surveyor_required = input_data.damage_amount > 10000

        # Expected settlement = damage minus ~15% deductible and depreciation
        expected_settlement = round(input_data.damage_amount * 0.85, 2)

        return ClaimResult(
            claim_id=claim_id,
            policy_number=input_data.policy_number,
            status="registered",
            incident_type=input_data.incident_type,
            damage_amount=input_data.damage_amount,
            expected_settlement=expected_settlement,
            surveyor_required=surveyor_required,
            registered_at=now.isoformat(),
            estimated_settlement_date=(now + timedelta(days=settlement_days)).strftime("%Y-%m-%d"),
            notes=(
                f"Claim registered successfully. Reference: {claim_id}. "
                f"{'A surveyor will be assigned within 24 hours.' if surveyor_required else 'Small claim — direct assessment.'}"
            ),
        )


class CheckClaimStatusTool(BaseTool):
    """Check the status of an existing insurance claim by claim ID."""

    name = "check_claim_status"
    description = "Check the current status, stage, and next steps for an existing claim."
    domains = ["insurance"]
    input_schema = CheckClaimInput
    output_schema = ClaimStatus

    async def execute(self, input_data: CheckClaimInput) -> ClaimStatus:
        # TODO: Replace with Claims Management System status API
        seed = hashlib.md5(input_data.claim_id.encode()).hexdigest()
        statuses = ["registered", "under_review", "surveyor_assigned", "approved", "payment_processing"]
        stages = ["Document Verification", "Survey Assessment", "Claim Assessment", "Manager Approval", "Finance Processing"]

        status_idx = int(seed[0], 16) % len(statuses)
        surveyor_names = ["Rajesh Kumar", "Sunita Verma", "Arun Nair", "Meena Joshi"]
        surveyor_idx = int(seed[2], 16) % len(surveyor_names)

        approved_amount = None
        if status_idx >= 3:
            approved_amount = round(int(seed[4:8], 16) / 65535 * 500000, 2)

        visit_date = (datetime.utcnow() + timedelta(days=int(seed[1], 16) % 7 + 1)).strftime("%Y-%m-%d")

        return ClaimStatus(
            claim_id=input_data.claim_id,
            policy_number=f"POL-{seed[8:14].upper()}",
            status=statuses[status_idx],
            stage=stages[min(status_idx, len(stages)-1)],
            damage_amount=round(int(seed[4:8], 16) / 65535 * 600000, 2),
            approved_amount=approved_amount,
            surveyor_name=surveyor_names[surveyor_idx] if status_idx >= 2 else None,
            surveyor_visit_date=visit_date if status_idx >= 2 else None,
            last_updated=datetime.utcnow().isoformat(),
            next_action="Surveyor assessment scheduled" if status_idx == 2 else "Awaiting document verification",
        )


class AssignSurveyorTool(BaseTool):
    """Assign a surveyor to assess damage for a claim."""

    name = "assign_surveyor"
    description = "Assign a licensed surveyor to assess damage for a claim. Returns surveyor details and visit schedule."
    domains = ["insurance"]
    input_schema = AssignSurveyorInput
    output_schema = SurveyorAssignment

    async def execute(self, input_data: AssignSurveyorInput) -> SurveyorAssignment:
        # TODO: Replace with Surveyor Management System API
        seed = hashlib.md5(input_data.claim_id.encode()).hexdigest()
        surveyors = [
            ("SRV-001", "Rajesh Kumar", "+91-98765-43210"),
            ("SRV-002", "Sunita Verma", "+91-87654-32109"),
            ("SRV-003", "Arun Nair", "+91-76543-21098"),
        ]
        idx = int(seed[0], 16) % len(surveyors)
        srv_id, srv_name, srv_phone = surveyors[idx]

        return SurveyorAssignment(
            claim_id=input_data.claim_id,
            surveyor_id=srv_id,
            surveyor_name=srv_name,
            surveyor_phone=srv_phone,
            assigned_at=datetime.utcnow().isoformat(),
            expected_visit_date=(datetime.utcnow() + timedelta(days=int(seed[1], 16) % 5 + 2)).strftime("%Y-%m-%d"),
        )
