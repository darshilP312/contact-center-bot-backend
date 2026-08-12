from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.tools.base import BaseTool


class RouteToHumanInput(BaseModel):
    session_id: str
    customer_id: Optional[str] = None
    escalation_reason: str
    final_sentiment: str
    transcript_summary: str
    priority: str = "normal"


class HandoffResult(BaseModel):
    session_id: str
    handoff_id: str
    queue_position: int
    estimated_wait_minutes: int
    agent_id: Optional[str] = None
    status: str
    timestamp: str


class QueueStatusInput(BaseModel):
    queue_name: str = "general"


class QueueStatus(BaseModel):
    queue_name: str
    active_agents: int
    customers_waiting: int
    estimated_wait_minutes: int
    status: str


class RouteToHumanAgentTool(BaseTool):
    """Route the customer to a human agent with full escalation context."""

    name = "route_to_human_agent"
    description = (
        "Escalate the customer to a human agent. Provides full session context "
        "including transcript summary, intent, and sentiment to the receiving agent. "
        "Use when the issue cannot be resolved by the AI."
    )
    domains = ["*"]
    input_schema = RouteToHumanInput
    output_schema = HandoffResult

    async def execute(self, input_data: RouteToHumanInput) -> HandoffResult:
        # TODO: Replace with Contact Center routing API call (Amazon Connect / Genesys / Avaya / Five9)
        seed = hashlib.md5(input_data.session_id.encode()).hexdigest()
        queue_pos = int(seed[0:2], 16) % 10 + 1
        wait_time = queue_pos * 3  # ~3 minutes per person in queue

        return HandoffResult(
            session_id=input_data.session_id,
            handoff_id=f"HND-{seed[:6].upper()}",
            queue_position=queue_pos,
            estimated_wait_minutes=wait_time,
            agent_id=None,  # Agent not yet assigned
            status="queued",
            timestamp=datetime.utcnow().isoformat(),
        )


class GetQueueStatusTool(BaseTool):
    """Check the current human agent queue status and wait time."""

    name = "get_queue_status"
    description = "Get the current number of customers waiting and estimated wait time for human agents."
    domains = ["*"]
    input_schema = QueueStatusInput
    output_schema = QueueStatus

    async def execute(self, input_data: QueueStatusInput) -> QueueStatus:
        # TODO: Replace with Contact Center real-time queue API
        seed = hashlib.md5(input_data.queue_name.encode()).hexdigest()
        waiting = int(seed[0:2], 16) % 8
        agents = int(seed[2:4], 16) % 5 + 2

        return QueueStatus(
            queue_name=input_data.queue_name,
            active_agents=agents,
            customers_waiting=waiting,
            estimated_wait_minutes=max(1, waiting * 3),
            status="open" if agents > 0 else "closed",
        )
