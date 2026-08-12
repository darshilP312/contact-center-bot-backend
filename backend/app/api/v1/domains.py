from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class DomainSummary(BaseModel):
    domain_id: str
    domain_name: str
    version: str
    intents_count: int
    enabled_tools: list[str]
    has_rag: bool


class DomainsResponse(BaseModel):
    domains: list[DomainSummary]


@router.get("", response_model=DomainsResponse, summary="List loaded domains")
async def list_domains(request: Request) -> DomainsResponse:
    """
    List all loaded domain plugins.

    Returns metadata for each domain that was discovered and loaded at startup.
    """
    domain_loader = request.app.state.domain_loader
    summaries = []

    for domain_id, config in domain_loader.domains.items():
        summaries.append(
            DomainSummary(
                domain_id=domain_id,
                domain_name=config.get("domain_name", domain_id),
                version=config.get("version", "unknown"),
                intents_count=len(config.get("intents", [])),
                enabled_tools=config.get("enabled_tools", []),
                has_rag=bool(config.get("rag", {}).get("knowledge_dir")),
            )
        )

    return DomainsResponse(domains=summaries)
