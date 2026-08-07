"""
router.py — FastAPI sub-app: mount all mock tool endpoints for direct HTTP access.
Useful for testing tools independently without the orchestrator.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from app.tools import lookup_customer as lc_module
from app.tools import check_outage as co_module
from app.tools import run_diagnostics as rd_module
from app.tools import book_engineer as be_module
from app.tools import refund_payment as rp_module
from app.tools import create_ticket as ct_module

router = APIRouter(prefix="/tools", tags=["Mock Enterprise Tools"])


# ── Request models ────────────────────────────────────────────────────────────

class LookupCustomerReq(BaseModel):
    account_no: Optional[str] = None
    phone: Optional[str] = None
    customer_id: Optional[str] = None


class CheckOutageReq(BaseModel):
    area_code: str
    customer_id: Optional[str] = None


class RunDiagnosticsReq(BaseModel):
    customer_id: Optional[str] = None
    session_id: Optional[str] = None


class BookEngineerReq(BaseModel):
    customer_id: Optional[str] = None
    reason: Optional[str] = "Technical issue"
    priority: Optional[str] = "standard"


class RefundPaymentReq(BaseModel):
    customer_id: Optional[str] = None
    amount: float
    reason: Optional[str] = "Customer request"
    invoice_id: Optional[str] = None


class CreateTicketReq(BaseModel):
    customer_id: Optional[str] = None
    session_id: Optional[str] = None
    intent: Optional[str] = "general"
    summary: Optional[str] = ""
    priority: Optional[str] = "medium"
    ticket_type: Optional[str] = "incident"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/lookup_customer", summary="Look up customer by account/phone")
def api_lookup_customer(req: LookupCustomerReq):
    return lc_module.lookup_customer(**req.model_dump())


@router.post("/check_outage", summary="Check for network outages in an area")
def api_check_outage(req: CheckOutageReq):
    return co_module.check_outage(**req.model_dump())


@router.post("/run_diagnostics", summary="Run remote line diagnostics")
def api_run_diagnostics(req: RunDiagnosticsReq):
    return rd_module.run_diagnostics(**req.model_dump())


@router.post("/book_engineer", summary="Schedule a field engineer visit")
def api_book_engineer(req: BookEngineerReq):
    return be_module.book_engineer(**req.model_dump())


@router.post("/refund_payment", summary="Process a payment refund (policy-gated)")
def api_refund_payment(req: RefundPaymentReq):
    return rp_module.refund_payment(**req.model_dump())


@router.post("/create_ticket", summary="Create a support ticket")
def api_create_ticket(req: CreateTicketReq):
    return ct_module.create_ticket(**req.model_dump())
