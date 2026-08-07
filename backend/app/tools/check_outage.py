"""
check_outage.py — Mock network operations: check for known area outages.
Returns outage details if one is active in the customer's area code.
"""

from app.tools.contracts import ToolResult, ok_result

ACTIVE_OUTAGES: dict[str, dict] = {
    "MH400002": {
        "outage_id": "OUT-4521",
        "description": "Fibre cable cut on Link Road. Field crews on-site.",
        "eta_hours": 4,
        "severity": "high",
        "affected_services": ["broadband", "voice"],
    },
}


def check_outage(
    area_code: str = None,
    customer_id: str = None,
    **kwargs,
) -> ToolResult:
    """
    Check if there is a known network outage in the customer's area.
    Returns outage details if found, or a clear-signal response.
    """
    if area_code and area_code in ACTIVE_OUTAGES:
        return ok_result({
            "outage": True,
            "outage_found": True,
            **ACTIVE_OUTAGES[area_code],
            "message": (
                f"We have a known outage in your area (ID: {ACTIVE_OUTAGES[area_code]['outage_id']}). "
                f"Estimated resolution in {ACTIVE_OUTAGES[area_code]['eta_hours']} hours."
            ),
        })

    return ok_result({
        "outage": False,
        "outage_found": False,
        "area_code": area_code,
        "message": "No known outages detected in your area.",
    })
