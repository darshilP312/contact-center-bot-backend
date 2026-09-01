"""
RAGManager — Production-grade retrieval using the full RAG engine from backend/RAG/.

Replaces the old ChromaDB stub that searched a near-empty `.chroma_db/` collection.
Now delegates to RAGSearchEngine (ChromaDB + FAISS + RRF + Redis caching) which has
the full knowledge base (motor, health, home insurance — 19 files, 350+ chunks).

The public API preserves backward compatibility with agent.py callers:
  - RAGResult.to_context_block() — same interface as before
  - RAGResult.passages — list of RetrievedPassage with .title/.score/.category/.content
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeRetrieval

logger = logging.getLogger(__name__)


# ─── Data Classes (preserved interface for agent.py) ──────────────────────────

@dataclass
class RetrievedPassage:
    doc_id: str
    chunk_id: str
    title: str
    category: str
    content: str
    score: float   # cosine similarity [0, 1]


@dataclass
class RAGResult:
    query: str
    passages: list[RetrievedPassage] = field(default_factory=list)

    def to_context_block(self) -> str:
        if not self.passages:
            return ""
        lines = ["[KNOWLEDGE BASE]:"]
        for p in self.passages:
            lines.append(f"  [{p.category.upper()}] {p.title}: {p.content}")
        return "\n".join(lines)


# ─── RAGManager ───────────────────────────────────────────────────────────────

class RAGManager:
    """
    Semantic RAG retrieval backed by the full production RAG engine.

    Usage (unchanged from old interface):
        manager = RAGManager()
        result = await manager.retrieve(query, query_embedding, db, conversation_id)

    The query_embedding parameter is accepted for backward compatibility but is no longer
    used — the RAG engine handles embedding internally using the same all-MiniLM-L6-v2 model.
    """

    async def retrieve(
        self,
        query: str,
        query_embedding: list[float] | None = None,  # kept for compat, unused
        db: AsyncSession | None = None,
        conversation_id=None,
        top_k: int = 3,
        domain: str | None = None,
    ) -> RAGResult:
        """
        Full retrieval pipeline using production RAG engine:
        1. Semantic search via ChromaDB + FAISS (RRF fusion) + Redis cache
        2. Optionally log retrievals to knowledge_retrieval table
        """
        try:
            from app.orchestrator.rag import rag_engine  # noqa: PLC0415

            if not rag_engine.is_ready:
                logger.warning("RAG engine not initialized — returning empty results")
                return RAGResult(query=query)

            # Infer domain from query if not provided
            if domain is None:
                domain = _infer_domain(query)

            rag_results = await rag_engine.search(
                query=query,
                top_k=top_k,
                domain=domain,
            )

        except Exception as exc:
            logger.error("RAG search failed: %s", exc)
            return RAGResult(query=query)

        # Convert RAGSearchEngine results to the preserved RetrievedPassage interface
        passages: list[RetrievedPassage] = []
        for r in rag_results:
            passages.append(
                RetrievedPassage(
                    doc_id=r.metadata.get("section_id", ""),
                    chunk_id=r.source,
                    title=r.section_title or r.source,
                    category=_domain_to_category(r.domain),
                    content=r.content[:600],  # Trim for LLM context budget
                    score=r.score,
                )
            )

        # Persist retrieval log to PostgreSQL (audit trail)
        if passages and conversation_id and db is not None:
            for p in passages:
                try:
                    record = KnowledgeRetrieval(
                        conversation_id=conversation_id,
                        query=query,
                        doc_id=uuid.UUID(p.doc_id) if _is_valid_uuid(p.doc_id) else None,
                        passage=p.content[:500],
                        relevance_score=p.score,
                    )
                    db.add(record)
                    await db.commit()
                except Exception as exc:
                    logger.error("RAG retrieval persist error: %s", exc)

        logger.debug(
            "RAG retrieved %d passages for query='%s...' domain=%s",
            len(passages), query[:60], domain,
        )
        return RAGResult(query=query, passages=passages)


# ─── Helpers ──────────────────────────────────────────────────────────────────

_MOTOR_KEYWORDS = {
    "car", "vehicle", "motor", "bike", "accident", "garage", "ncb", "depreciation",
    "own damage", "third party", "tp", "od", "rto", "chassis", "engine", "roadside",
    "towing", "cashless repair", "claim motor", "comprehensive", "zero dep",
}
_HEALTH_KEYWORDS = {
    "health", "hospital", "medical", "claim health", "doctor", "surgery",
    "icu", "cashless health", "pre-existing", "ped", "copay", "deductible",
    "maternity", "daycare", "critical illness", "sum insured", "tpa",
    "network hospital", "health shield", "covid", "treatment",
}
_HOME_KEYWORDS = {
    "home", "house", "property", "flat", "apartment", "earthquake", "flood",
    "fire home", "burglary", "theft home", "building", "contents", "restoration",
    "home protector", "reinstatement",
}


def _infer_domain(query: str) -> str | None:
    """
    Heuristic domain detection so the RRF engine gets a focused metadata filter.
    Returns None if domain is ambiguous (full-corpus search).
    """
    q = query.lower()
    tokens = set(q.split())

    motor_hits = sum(1 for kw in _MOTOR_KEYWORDS if kw in q)
    health_hits = sum(1 for kw in _HEALTH_KEYWORDS if kw in q)
    home_hits   = sum(1 for kw in _HOME_KEYWORDS   if kw in q)

    best = max(motor_hits, health_hits, home_hits)
    if best == 0:
        return None  # General query — search across all domains
    if motor_hits == best:
        return "motor_insurance"
    if health_hits == best:
        return "health_insurance"
    return "home_insurance"


def _domain_to_category(domain: str) -> str:
    mapping = {
        "motor_insurance": "motor",
        "health_insurance": "health",
        "home_insurance": "home",
        "general_insurance": "general",
    }
    return mapping.get(domain, domain.replace("_insurance", ""))


def _is_valid_uuid(val: str) -> bool:
    try:
        uuid.UUID(val)
        return True
    except (ValueError, AttributeError):
        return False
