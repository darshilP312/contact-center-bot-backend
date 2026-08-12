"""
run_diagnostics.py — Mock remote diagnostics: simulate automated line tests.
Returns pass/fail with signal quality data. Simulates realistic failure rates.
"""

import random
from app.tools.contracts import ToolResult, ok_result

_SCENARIOS = [
    {
        "diagnostic_passed": True,
        "signal_strength": "good",
        "snr_db": 28.5,
        "issue_found": False,
        "recommendation": "Connection is healthy. Issue may have self-resolved.",
    },
    {
        "diagnostic_passed": False,
        "signal_strength": "weak",
        "snr_db": 11.2,
        "issue_found": True,
        "issue": "Low signal-to-noise ratio on copper pair",
        "recommendation": "Remote fix not possible. Consider engineer visit.",
    },
    {
        "diagnostic_passed": False,
        "signal_strength": "none",
        "snr_db": 0.0,
        "issue_found": True,
        "issue": "Router not responding to ping (possible hardware fault)",
        "recommendation": "Remote fix not possible. Engineer visit required.",
    },
]


def run_diagnostics(
    customer_id: str = None,
    session_id: str = None,
    **kwargs,
) -> ToolResult:
    """
    Run remote diagnostic tests on customer equipment.
    Simulates 30% pass / 70% fail for realistic demo behaviour.
    """
    scenario = random.choices(_SCENARIOS, weights=[30, 40, 30])[0]
    return ok_result({**scenario, "customer_id": customer_id})
