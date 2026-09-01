"""
Hybrid RAG Search Engine — Main Orchestrator

Combines ChromaDB (semantic search with metadata filtering) + FAISS (fast ANN retrieval)
+ Redis (query result caching) into a single, production-grade search interface.

Uses Reciprocal Rank Fusion (RRF) to merge results from both retrieval sources.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .cache import RAGCache
from .config import RAGConfig, rag_config
from .document_loader import DocumentLoader, KBChunk
from .faiss_index import FAISSIndex
from .vector_store import ChromaVectorStore

logger = logging.getLogger("rag.search_engine")


@dataclass
class RAGResult:
    """A single RAG search result with content and provenance metadata."""

    content: str
    source: str              # e.g., "motor_insurance_kb.json"
    domain: str              # e.g., "motor_insurance"
    section_title: str       # e.g., "Zero Depreciation Cover"
    doc_type: str            # "faq" | "section" | "paragraph"
    score: float             # 0.0 to 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "source": self.source,
            "domain": self.domain,
            "section_title": self.section_title,
            "doc_type": self.doc_type,
            "score": round(self.score, 4),
            "metadata": self.metadata,
        }


class RAGSearchEngine:
    """
    Production-grade RAG search engine combining ChromaDB + FAISS + Redis.

    Features:
    - Dual retrieval: ChromaDB (metadata-aware) + FAISS (speed)
    - Reciprocal Rank Fusion for result merging
    - Redis caching for repeated queries
    - Graceful degradation at every layer
    - Async-safe for 30-40+ concurrent queries
    - Hot-reload support for knowledge base updates
    """

    def __init__(self, config: Optional[RAGConfig] = None) -> None:
        self.config = config or rag_config
        self.document_loader = DocumentLoader(self.config)
        self.vector_store = ChromaVectorStore(self.config)
        self.faiss_index = FAISSIndex(self.config)
        self.cache = RAGCache(self.config)

        self._chunks: List[KBChunk] = []
        self._chunk_map: Dict[str, KBChunk] = {}  # ID → chunk for result enrichment
        self._initialized = False
        self._lock = asyncio.Lock()

    async def initialize(self) -> Dict[str, Any]:
        """
        Full initialization pipeline:
        1. Load JSON knowledge base documents
        2. Chunk documents
        3. Upsert into ChromaDB
        4. Build FAISS index from ChromaDB embeddings
        5. Connect Redis cache

        Returns:
            Status dict with component health information.
        """
        async with self._lock:
            status: Dict[str, Any] = {}

            try:
                # 1. Load and chunk documents
                self._chunks = self.document_loader.load_all()
                self._chunk_map = {c.id: c for c in self._chunks}
                status["documents_loaded"] = len(self._chunks)
                logger.info(f"Loaded {len(self._chunks)} document chunks")

                # 2. Initialize ChromaDB and upsert
                self.vector_store.initialize()
                existing_count = self.vector_store.count()

                if existing_count < len(self._chunks):
                    upserted = self.vector_store.upsert_documents(self._chunks)
                    status["chromadb_upserted"] = upserted
                    logger.info(f"Upserted {upserted} chunks into ChromaDB")
                else:
                    status["chromadb_upserted"] = 0
                    logger.info(
                        f"ChromaDB already has {existing_count} docs, skipping upsert"
                    )
                status["chromadb"] = "healthy"

                # 3. Build FAISS index from ChromaDB embeddings
                try:
                    embeddings, ids = self.vector_store.get_all_embeddings()
                    if embeddings.size > 0:
                        self.faiss_index.build_index(embeddings, ids)
                        status["faiss"] = "healthy"
                        status["faiss_docs"] = self.faiss_index.doc_count
                    else:
                        status["faiss"] = "empty"
                except Exception as e:
                    logger.warning(f"FAISS index build failed: {e}")
                    status["faiss"] = f"degraded: {e}"

                # 4. Connect Redis cache (optional, graceful degradation)
                try:
                    redis_ok = await self.cache.initialize()
                    status["redis"] = "healthy" if redis_ok else "unavailable (graceful)"
                except Exception as e:
                    logger.warning(f"Redis connection failed: {e}")
                    status["redis"] = f"unavailable: {e}"

                self._initialized = True
                status["status"] = "ready"
                logger.info(f"RAG Search Engine initialized: {status}")

            except Exception as e:
                status["status"] = f"error: {e}"
                logger.error(f"RAG initialization failed: {e}", exc_info=True)

            return status

    async def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        domain: Optional[str] = None,
        doc_type: Optional[str] = None,
    ) -> List[RAGResult]:
        """
        Hybrid search combining ChromaDB + FAISS with Redis caching.

        Pipeline:
        1. Check Redis cache → return on hit
        2. Run ChromaDB semantic search (metadata-filtered)
        3. Run FAISS ANN search (pure speed)
        4. Merge via Reciprocal Rank Fusion
        5. Cache results in Redis
        6. Return top-K results

        Args:
            query: Natural language search query
            top_k: Number of results (default from config)
            domain: Optional domain filter ("motor_insurance", "health_insurance")
            doc_type: Optional doc type filter ("faq", "section", "paragraph")

        Returns:
            List of RAGResult objects sorted by relevance score
        """
        if not self._initialized:
            logger.warning("RAG engine not initialized, returning empty results")
            return []

        k = top_k or self.config.top_k

        # 1. Check Redis cache
        cached = await self.cache.get(query, domain)
        if cached:
            return [
                RAGResult(
                    content=r["content"],
                    source=r.get("source", ""),
                    domain=r.get("domain", ""),
                    section_title=r.get("section_title", ""),
                    doc_type=r.get("doc_type", ""),
                    score=r.get("score", 0.0),
                    metadata=r.get("metadata", {}),
                )
                for r in cached[:k]
            ]

        # 2. ChromaDB semantic search
        chroma_results = []
        try:
            chroma_results = self.vector_store.search(
                query=query,
                top_k=k * 2,  # Over-fetch for better RRF merge
                domain_filter=domain,
                doc_type_filter=doc_type,
            )
        except Exception as e:
            logger.warning(f"ChromaDB search error: {e}")

        # 3. FAISS ANN search
        faiss_results: List[Dict[str, Any]] = []
        try:
            if self.faiss_index.is_ready:
                query_embedding = self.vector_store.embed_query(query)
                faiss_hits = self.faiss_index.search(query_embedding, top_k=k * 2)

                for doc_id, score in faiss_hits:
                    chunk = self._chunk_map.get(doc_id)
                    if chunk:
                        # Apply domain filter manually for FAISS (no built-in metadata filter)
                        if domain and chunk.domain != domain:
                            continue
                        if doc_type and chunk.doc_type != doc_type:
                            continue
                        faiss_results.append(
                            {
                                "id": doc_id,
                                "content": chunk.content,
                                "metadata": {
                                    "domain": chunk.domain,
                                    "section_id": chunk.section_id,
                                    "section_title": chunk.section_title,
                                    "doc_type": chunk.doc_type,
                                    "source_file": chunk.source_file,
                                },
                                "score": score,
                                "source": "faiss",
                            }
                        )
        except Exception as e:
            logger.warning(f"FAISS search error: {e}")

        # 4. Merge via Reciprocal Rank Fusion (RRF)
        merged = self._reciprocal_rank_fusion(chroma_results, faiss_results, k=k)

        # 5. Convert to RAGResult objects
        results: List[RAGResult] = []
        for item in merged:
            meta = item.get("metadata", {})
            raw_score = item.get("score", item.get("rrf_score", 0.0))
            result = RAGResult(
                content=item["content"],
                source=meta.get("source_file", ""),
                domain=meta.get("domain", ""),
                section_title=meta.get("section_title", ""),
                doc_type=meta.get("doc_type", ""),
                score=raw_score,
                metadata={**meta, "rrf_score": item.get("rrf_score", 0.0)},
            )
            results.append(result)

        # 6. Cache results in Redis
        if results:
            await self.cache.set(
                query,
                [r.to_dict() for r in results],
                domain=domain,
            )

        logger.info(
            f"RAG search: query='{query[:60]}...', domain={domain}, "
            f"chroma={len(chroma_results)}, faiss={len(faiss_results)}, "
            f"merged={len(results)}"
        )

        return results

    def _reciprocal_rank_fusion(
        self,
        chroma_results: List[Dict[str, Any]],
        faiss_results: List[Dict[str, Any]],
        k: int = 5,
        rrf_k: int = 60,
    ) -> List[Dict[str, Any]]:
        """
        Merge results from two retrieval sources using Reciprocal Rank Fusion.

        RRF score = sum(1 / (rrf_k + rank)) for each source where the doc appears.
        This balances results from different systems without requiring score normalization.

        Args:
            chroma_results: Results from ChromaDB
            faiss_results: Results from FAISS
            k: Final number of results to return
            rrf_k: RRF constant (default 60, standard in literature)

        Returns:
            Merged and reranked results
        """
        doc_scores: Dict[str, Dict[str, Any]] = {}

        # Score ChromaDB results
        for rank, result in enumerate(chroma_results):
            doc_id = result["id"]
            rrf_score = 1.0 / (rrf_k + rank + 1)
            if doc_id not in doc_scores:
                doc_scores[doc_id] = {**result, "rrf_score": 0.0}
            doc_scores[doc_id]["rrf_score"] += rrf_score

        # Score FAISS results
        for rank, result in enumerate(faiss_results):
            doc_id = result["id"]
            rrf_score = 1.0 / (rrf_k + rank + 1)
            if doc_id not in doc_scores:
                doc_scores[doc_id] = {**result, "rrf_score": 0.0}
            doc_scores[doc_id]["rrf_score"] += rrf_score

        # Sort by RRF score descending
        merged = sorted(doc_scores.values(), key=lambda x: x["rrf_score"], reverse=True)

        return merged[:k]

    async def reload_documents(self) -> Dict[str, Any]:
        """
        Hot-reload: re-read KB files, re-chunk, re-embed, rebuild FAISS, flush cache.
        Thread-safe via async lock.
        """
        async with self._lock:
            logger.info("Hot-reloading RAG knowledge base...")

            if not self._initialized:
                return await self.initialize()

            # Clear existing data
            self.vector_store.clear()
            await self.cache.invalidate()

            # Re-load everything
            self._chunks = self.document_loader.load_all()
            self._chunk_map = {c.id: c for c in self._chunks}

            upserted = self.vector_store.upsert_documents(self._chunks)

            embeddings, ids = self.vector_store.get_all_embeddings()
            if embeddings.size > 0:
                self.faiss_index.rebuild(embeddings, ids)

            status = {
                "reloaded": True,
                "chunks": len(self._chunks),
                "upserted": upserted,
                "faiss_rebuilt": self.faiss_index.is_ready,
            }
            logger.info(f"RAG hot-reload complete: {status}")
            return status

    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check for all RAG components."""
        return {
            "initialized": self._initialized,
            "documents_loaded": len(self._chunks),
            "chromadb": {
                "status": "healthy" if self.vector_store.ping() else "unhealthy",
                "doc_count": self.vector_store.count(),
            },
            "faiss": {
                "status": "healthy" if self.faiss_index.is_ready else "not_built",
                "doc_count": self.faiss_index.doc_count,
            },
            "redis": {
                "status": "healthy" if await self.cache.ping() else "unavailable",
                "enabled": self.config.enable_redis,
            },
        }

    @property
    def is_ready(self) -> bool:
        return self._initialized

    async def close(self) -> None:
        """Graceful shutdown — close Redis connections."""
        await self.cache.close()
        logger.info("RAG Search Engine shut down")
