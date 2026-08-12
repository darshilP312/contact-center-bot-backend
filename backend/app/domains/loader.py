from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from app.core.logging import get_logger

logger = get_logger("domains.loader")


class DomainLoader:
    """
    Domain plugin discovery and loader.

    Scans the domains directory at startup, loads all domain.yaml files,
    and makes domain configs available to the orchestrator, tool registry,
    and RAG pipeline.

    Domain plugins are discovered automatically — no registration required.
    Any directory under domains/ containing a domain.yaml is loaded.
    """

    def __init__(self, domains_dir: str = "domains") -> None:
        # Resolve relative to backend/app/
        self.domains_dir = Path(__file__).parent.parent / domains_dir
        self.domains: dict[str, dict[str, Any]] = {}
        self.workflows: dict[str, dict[str, Any]] = {}  # domain_id -> workflow_id -> config

    async def load_all(self) -> None:
        """Discover and load all domain plugins."""
        if not self.domains_dir.exists():
            logger.warning(
                "Domains directory not found",
                node="domains.loader",
                path=str(self.domains_dir),
            )
            return

        for entry in sorted(self.domains_dir.iterdir()):
            if entry.is_dir() and not entry.name.startswith("_"):
                domain_yaml = entry / "domain.yaml"
                if domain_yaml.exists():
                    await self._load_domain(entry)

        logger.info(
            "Domain loading complete",
            node="domains.loader",
            loaded_domains=list(self.domains.keys()),
        )

    async def _load_domain(self, domain_dir: Path) -> None:
        """Load a single domain plugin from its directory."""
        domain_yaml = domain_dir / "domain.yaml"

        try:
            with open(domain_yaml, encoding="utf-8") as f:
                config = yaml.safe_load(f)

            domain_id = config["domain_id"]
            self.domains[domain_id] = config

            # Load workflows
            workflows_dir = domain_dir / "workflows"
            self.workflows[domain_id] = {}
            if workflows_dir.exists():
                for wf_file in workflows_dir.glob("*.yaml"):
                    with open(wf_file, encoding="utf-8") as f:
                        wf_config = yaml.safe_load(f)
                    wf_id = wf_config.get("workflow_id", wf_file.stem)
                    self.workflows[domain_id][wf_id] = wf_config

            logger.info(
                "Domain loaded",
                node="domains.loader",
                domain_id=domain_id,
                intents=len(config.get("intents", [])),
                workflows=len(self.workflows[domain_id]),
                tools=len(config.get("enabled_tools", [])),
            )

        except Exception as e:
            logger.error(
                "Failed to load domain",
                node="domains.loader",
                domain_dir=str(domain_dir),
                error=str(e),
            )

    def get_domain(self, domain_id: str) -> dict[str, Any] | None:
        """Get domain configuration by ID."""
        return self.domains.get(domain_id)

    def get_intent(self, domain_id: str, intent_name: str) -> dict[str, Any] | None:
        """Get a specific intent config from a domain."""
        domain = self.get_domain(domain_id)
        if not domain:
            return None
        for intent in domain.get("intents", []):
            if intent["name"] == intent_name:
                return intent
        return None

    def get_workflow(self, domain_id: str, workflow_id: str) -> dict[str, Any] | None:
        """Get a workflow config for a domain."""
        return self.workflows.get(domain_id, {}).get(workflow_id)

    def get_intent_taxonomy(self, domain_id: str) -> list[dict[str, Any]]:
        """Get all intents for a domain (for LLM prompts)."""
        domain = self.get_domain(domain_id)
        if not domain:
            return []
        return domain.get("intents", [])

    def get_knowledge_dir(self, domain_id: str) -> str | None:
        """Get the knowledge directory path for RAG indexing."""
        domain = self.get_domain(domain_id)
        if not domain:
            return None
        rag_config = domain.get("rag", {})
        knowledge_dir = rag_config.get("knowledge_dir")
        if knowledge_dir:
            # Resolve relative to backend/app/
            return str(Path(__file__).parent.parent / knowledge_dir)
        return None
