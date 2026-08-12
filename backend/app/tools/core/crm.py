from __future__ import annotations

import hashlib
from typing import Literal, Optional

from pydantic import BaseModel

from app.tools.base import BaseTool


# ─── Input/Output Schemas ─────────────────────────────────────────────────────

class LookupCustomerInput(BaseModel):
    customer_id: str


class CustomerProfile(BaseModel):
    customer_id: str
    name: str
    email: str
    phone: str  # PII — masked in logs
    tier: Literal["standard", "premium", "enterprise"]
    account_no: str  # PII — masked in logs
    city: str
    registered_since: str


class VerifyCustomerInput(BaseModel):
    customer_id: str
    dob: str                # Date of birth (YYYY-MM-DD)
    last_4_account: str     # Last 4 digits of account number


class VerificationResult(BaseModel):
    customer_id: str
    verified: bool
    reason: Optional[str] = None


# ─── Tool Implementations ─────────────────────────────────────────────────────

class LookupCustomerTool(BaseTool):
    """Look up a customer profile by customer ID."""

    name = "lookup_customer"
    description = (
        "Look up a customer's profile and account information by their customer ID. "
        "Returns name, tier, contact info, and account number."
    )
    domains = ["*"]  # Available to all domains
    input_schema = LookupCustomerInput
    output_schema = CustomerProfile

    async def execute(self, input_data: LookupCustomerInput) -> CustomerProfile:
        # TODO: Replace with CRM API call (Salesforce / SAP CRM / Oracle CX)
        seed = hashlib.md5(input_data.customer_id.encode()).hexdigest()

        tiers = ["standard", "premium", "enterprise"]
        cities = ["Mumbai", "Delhi", "Bangalore", "Chennai", "Hyderabad", "Pune"]
        names = ["Arjun Sharma", "Priya Patel", "Rahul Gupta", "Anita Singh", "Vikram Kumar"]

        tier_idx = int(seed[0], 16) % 3
        name_idx = int(seed[1], 16) % len(names)
        city_idx = int(seed[2], 16) % len(cities)
        account_suffix = seed[4:8].upper()
        email_prefix = names[name_idx].lower().replace(" ", ".")

        return CustomerProfile(
            customer_id=input_data.customer_id,
            name=names[name_idx],
            email=f"{email_prefix}@email.example.com",
            phone=f"+91-9{seed[4:13]}",
            tier=tiers[tier_idx],
            account_no=f"ACC-{account_suffix}-{seed[8:12].upper()}",
            city=cities[city_idx],
            registered_since=f"20{int(seed[12:14], 16) % 24 + 1:02d}-{int(seed[14:16], 16) % 12 + 1:02d}-01",
        )


class VerifyCustomerTool(BaseTool):
    """Verify customer identity using date of birth and last 4 account digits."""

    name = "verify_customer"
    description = (
        "Verify a customer's identity using their date of birth and last 4 digits "
        "of their account number. Returns verification status."
    )
    domains = ["*"]  # Available to all domains
    input_schema = VerifyCustomerInput
    output_schema = VerificationResult

    async def execute(self, input_data: VerifyCustomerInput) -> VerificationResult:
        # TODO: Replace with CRM identity verification API call
        # Mock: verification succeeds if last_4_account is 4 digits and dob is valid format
        is_valid_dob = len(input_data.dob) == 10 and input_data.dob[4] == "-"
        is_valid_account = len(input_data.last_4_account) == 4 and input_data.last_4_account.isdigit()

        # Deterministic: verification based on customer_id hash
        seed = hashlib.md5(input_data.customer_id.encode()).hexdigest()
        verified = is_valid_dob and is_valid_account and int(seed[0], 16) > 2  # ~87% success rate

        return VerificationResult(
            customer_id=input_data.customer_id,
            verified=verified,
            reason=None if verified else "Identity verification failed — please check your details",
        )
