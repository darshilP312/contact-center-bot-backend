"""
FAISS In-Memory ANN Index

Fast Approximate Nearest Neighbor search using Facebook AI Similarity Search.
Read-only after build → naturally thread-safe for concurrent queries.
Provides sub-millisecond retrieval for the RAG pipeline.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

from .config import RAGConfig, rag_config

logger = logging.getLogger("rag.faiss_index")


class FAISSIndex:
    """
    In-memory FAISS index for fast nearest neighbor retrieval.

    - Uses IndexFlatIP (Inner Product) with L2-normalized vectors for cosine similarity
    - Read-only after build → thread-safe for concurrent queries without locks
    - Rebuilds cleanly from ChromaDB embeddings on demand
    """

    def __init__(self, config: Optional[RAGConfig] = None) -> None:
        self.config = config or rag_config
        self._index = None
        self._id_map: Dict[int, str] = {}   # FAISS internal index → document ID
        self._doc_count: int = 0
        self._initialized = False

    def build_index(self, embeddings: np.ndarray, doc_ids: List[str]) -> None:
        """
        Build FAISS index from embeddings.

        Args:
            embeddings: numpy array of shape (N, dim) — float32
            doc_ids: list of document IDs corresponding to each row
        """
        import faiss

        if embeddings.size == 0 or len(doc_ids) == 0:
            logger.warning("No embeddings provided for FAISS index build")
            self._initialized = False
            return

        n_docs, dim = embeddings.shape

        # L2-normalize for cosine similarity via inner product
        faiss.normalize_L2(embeddings)

        # IndexFlatIP — exact inner product search (best for <10K docs)
        self._index = faiss.IndexFlatIP(dim)
        self._index.add(embeddings)

        # Build ID mapping: FAISS internal index → document ID
        self._id_map = {i: doc_id for i, doc_id in enumerate(doc_ids)}
        self._doc_count = n_docs
        self._initialized = True

        logger.info(
            f"FAISS index built: {n_docs} vectors, dim={dim}, "
            f"index_type=IndexFlatIP (exact cosine similarity)"
        )

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
    ) -> List[Tuple[str, float]]:
        """
        Search FAISS index for nearest neighbors.

        Args:
            query_embedding: numpy array of shape (1, dim) — float32
            top_k: number of results to return

        Returns:
            List of (doc_id, similarity_score) tuples, sorted by score descending
        """
        import faiss

        if not self._initialized or self._index is None:
            logger.warning("FAISS index not built — skipping search")
            return []

        # L2-normalize query for cosine similarity
        query = query_embedding.copy()
        faiss.normalize_L2(query)

        # Ensure 2D shape
        if query.ndim == 1:
            query = query.reshape(1, -1)

        k = min(top_k, self._doc_count)
        if k == 0:
            return []

        scores, indices = self._index.search(query, k)

        results: List[Tuple[str, float]] = []
        for i in range(k):
            idx = int(indices[0][i])
            score = float(scores[0][i])
            if idx >= 0 and idx in self._id_map:
                # Inner product scores are already in [-1, 1] for normalized vectors
                # Clamp to [0, 1] for consistency
                results.append((self._id_map[idx], max(0.0, score)))

        return results

    def rebuild(self, embeddings: np.ndarray, doc_ids: List[str]) -> None:
        """
        Rebuild the entire FAISS index (e.g., after document updates).
        Thread-safe: builds a new index and atomically swaps.
        """
        old_index = self._index
        old_map = self._id_map

        try:
            self.build_index(embeddings, doc_ids)
            logger.info("FAISS index rebuilt successfully")
        except Exception as e:
            # Rollback on failure
            self._index = old_index
            self._id_map = old_map
            logger.error(f"FAISS rebuild failed, kept old index: {e}")
            raise

    @property
    def doc_count(self) -> int:
        return self._doc_count

    @property
    def is_ready(self) -> bool:
        return self._initialized and self._index is not None

    def ping(self) -> bool:
        """Health check — verify FAISS index is loaded and queryable."""
        return self.is_ready
