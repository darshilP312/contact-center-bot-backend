"""
lookup_customer.py — Mock CRM: look up a customer by account number or phone.
Returns verified customer profile on success.
"""

from app.tools.contracts import ToolResult, ok_result, err_result

MOCK_CUSTOMERS: dict[str, dict] = {
    "ACC001": {
        "customer_id": "ACC001",
        "name": "Priya Sharma",
        "tier": "premium",
        "phone": "+919876543210",
        "area_code": "MH400001",
        "email": "priya.sharma@example.com",
        "account_no": "ACC001",
    },
    "ACC002": {
        "customer_id": "ACC002",
        "name": "Rahul Verma",
        "tier": "standard",
        "phone": "+919123456789",
        "area_code": "DL110001",
        "email": "rahul.verma@example.com",
        "account_no": "ACC002",
    },
}


def lookup_customer(
    account_no: str = None,
    phone: str = None,
    customer_id: str = None,
    **kwargs,
) -> ToolResult:
    """
    Look up a customer by account number, phone, or customer ID.
    Returns verified customer profile or a demo fallback for demos.
    """
    for cid, cdata in MOCK_CUSTOMERS.items():
        match = (
            (account_no and cdata.get("account_no") == account_no)
            or (phone and cdata.get("phone") == phone)
            or (customer_id and cid == customer_id)
        )
        if match:
            return ok_result({**cdata, "verified": True})

    # Demo fallback — keeps demos running even with unknown identifiers
    return ok_result({
        "customer_id": "ACC999",
        "name": "Demo Customer",
        "tier": "standard",
        "phone": phone or "unknown",
        "area_code": "GJ380001",
        "email": "demo@example.com",
        "account_no": account_no or "ACC999",
        "verified": True,
        "lookup_method": "demo_fallback",
    })
