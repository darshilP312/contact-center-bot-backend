"""
Knowledge Base Seeder — delegates to the production RAG engine.

This seeder uses the full RAGSearchEngine from app/orchestrator/rag/
which includes ChromaDB + FAISS + Redis caching and loads all 19 KB files
automatically from app/orchestrator/rag/data/knowledge_base/:
  - Motor: motor_insurance_kb.json, motor_plans_kb.json, motor_scenarios_kb.json
           motor_comprehensive_policy.md, motor_comprehensive_plus_policy.md,
           motor_third_party_policy.md, motor_insurance_policy_wording.md
  - Health: health_insurance_kb.json, health_shield_plans_kb.json, health_scenarios_kb.json
            health_shield_basic_policy.md, health_shield_gold_policy.md,
            health_shield_premium_policy.md, health_insurance_policy_wording.md
  - Home:   home_insurance_kb.json, home_protector_basic_policy.md, home_protector_elite_policy.md
  - General: general_insurance_kb.json

The RAG engine is a singleton (rag_engine) — initialize() is idempotent and skips
upsert if ChromaDB already has all chunks.

Vector store location: app/orchestrator/rag/data/chroma_db/
Knowledge base location: app/orchestrator/rag/data/knowledge_base/
"""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def seed_knowledge_base(db: AsyncSession) -> int:
    """
    Initialize the production RAG engine and load all KB documents into ChromaDB.

    Returns:
        Number of newly upserted chunks (0 if already indexed from a previous run).
    """
    try:
        from app.orchestrator.rag import rag_engine  # noqa: PLC0415

        status = await rag_engine.initialize()
        total_docs = status.get("documents_loaded", 0)
        newly_upserted = status.get("chromadb_upserted", 0)

        logger.info(
            "RAG engine initialized: %d chunks loaded, %d newly upserted | "
            "ChromaDB=%s FAISS=%s Redis=%s",
            total_docs,
            newly_upserted,
            status.get("chromadb", "?"),
            status.get("faiss", "?"),
            status.get("redis", "?"),
        )
        return newly_upserted

    except Exception as exc:
        logger.error("RAG seeder failed (non-fatal, app continues): %s", exc, exc_info=True)
        return 0
