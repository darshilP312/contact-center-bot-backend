from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Literal, Optional

from pydantic import BaseModel

from app.tools.base import BaseTool


class LookupPolicyInput(BaseModel):
    policy_number: str


class PolicyDetails(BaseModel):
    policy_number: str
    customer_id: str
    policy_type: str
    status: Literal["active", "expired", "cancelled", "suspended"]
    start_date: str
    end_date: str
    idv: float  # Insured Declared Value
    premium_annual: float
    next_renewal_date: str
    coverage_type: str
    add_ons: list[str]


class GetCoverageInput(BaseModel):
    policy_number: str
    coverage_type: str


class CoverageDetails(BaseModel):
    policy_number: str
    coverage_type: str
    is_covered: bool
    coverage_limit: float
    deductible: float
    exclusions: list[str]
    notes: str


class LookupPolicyTool(BaseTool):
    """Look up an insurance policy by policy number."""

    name = "lookup_policy"
    description = (
        "Retrieve full insurance policy details including coverage type, status, "
        "premium amount, IDV, renewal date, and add-ons."
    )
    domains = ["insurance"]
    input_schema = LookupPolicyInput
    output_schema = PolicyDetails

    async def execute(self, input_data: LookupPolicyInput) -> PolicyDetails:
        # TODO: Replace with Insurance Core System API call (POLICY360 / Majesco / DuckCreek)
        seed = hashlib.md5(input_data.policy_number.encode()).hexdigest()

        policy_types = ["Motor - Comprehensive", "Motor - Third Party", "Home - Standard", "Health - Family Floater"]
        coverage_types = ["comprehensive", "third_party", "property", "health"]
        add_on_options = [
            ["zero_depreciation", "engine_protect"],
            ["roadside_assistance"],
            ["contents_cover", "valuables_cover"],
            ["critical_illness", "personal_accident"],
        ]

        type_idx = int(seed[0], 16) % len(policy_types)
        start = datetime(2023, 1, 1) + timedelta(days=int(seed[2:4], 16) * 3)
        end = start + timedelta(days=365)
        renewal = end

        idv_base = int(seed[4:8], 16) % 15 + 5  # 5-20 lakhs range
        premium = round(idv_base * 0.025 * 100000, 0)  # ~2.5% of IDV

        return PolicyDetails(
            policy_number=input_data.policy_number,
            customer_id=f"CUST-{seed[:6].upper()}",
            policy_type=policy_types[type_idx],
            status="active",
            start_date=start.strftime("%Y-%m-%d"),
            end_date=end.strftime("%Y-%m-%d"),
            idv=idv_base * 100000.0,
            premium_annual=premium,
            next_renewal_date=renewal.strftime("%Y-%m-%d"),
            coverage_type=coverage_types[type_idx],
            add_ons=add_on_options[type_idx],
        )


class GetCoverageDetailsTool(BaseTool):
    """Get specific coverage details for a policy and coverage type."""

    name = "get_coverage_details"
    description = (
        "Check whether a specific coverage type is included in the policy, "
        "and retrieve coverage limit, deductible, and exclusions."
    )
    domains = ["insurance"]
    input_schema = GetCoverageInput
    output_schema = CoverageDetails

    async def execute(self, input_data: GetCoverageInput) -> CoverageDetails:
        # TODO: Replace with Insurance Core System coverage detail API
        seed = hashlib.md5(f"{input_data.policy_number}{input_data.coverage_type}".encode()).hexdigest()
        limit = (int(seed[0:2], 16) % 20 + 5) * 100000.0
        deductible = (int(seed[2:4], 16) % 5 + 1) * 1000.0

        return CoverageDetails(
            policy_number=input_data.policy_number,
            coverage_type=input_data.coverage_type,
            is_covered=int(seed[4], 16) > 2,  # ~81% covered
            coverage_limit=limit,
            deductible=deductible,
            exclusions=["normal_wear_and_tear", "drunk_driving", "illegal_modifications"],
            notes=f"Coverage up to ₹{limit:,.0f} with ₹{deductible:,.0f} deductible",
        )
