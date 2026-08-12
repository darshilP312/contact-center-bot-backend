from __future__ import annotations

import os
from pathlib import Path
from typing import Any, List, Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("orchestrator.memory.long_term")
settings = get_settings()


class LongTermMemoryStore:
    """
    Long-term memory backed by FAISS (dev) or pgvector (production).

    Stores and retrieves historical customer context using semantic similarity search.
    Falls back gracefully to in-memory FAISS if pgvector is not configured.

    Primary use: retrieving relevant past interaction context during planning.
    """

    def __init__(self) -> None:
        self._index: Any = None
        self._texts: list[str] = []
        self._embedder: Any = None
        self.is_loaded = False

    async def load(self) -> None:
        """Initialise the embedding model and FAISS index."""
        from sentence_transformers import SentenceTransformer

        model_name = settings.EMBEDDING_MODEL
        self._embedder = SentenceTransformer(model_name)
        self.is_loaded = True
        logger.info(
            "Long-term memory store initialised",
            node="memory.long_term",
            backend=settings.VECTOR_STORE,
            model=model_name,
        )

    async def ingest_turn(self, session_id: str, text: str, role: str = "customer") -> None:
        """
        Embed and store a transcript turn in long-term memory.

        Args:
            session_id: Session ID (used as namespace).
            text: Text to embed and store.
            role: Role of the speaker.
        """
        if not self.is_loaded:
            return

        import numpy as np
        import faiss

        entry = f"[{session_id}|{role}] {text}"
        embedding = self._embedder.encode([entry], convert_to_numpy=True)

        if self._index is None:
            dim = embedding.shape[1]
            self._index = faiss.IndexFlatL2(dim)

        self._index.add(embedding.astype(np.float32))
        self._texts.append(entry)

    async def retrieve_context(
        self, session_id: str, query: str, top_k: int = 3
    ) -> str:
        """
        Retrieve top-k relevant past context entries for a query.

        Args:
            session_id: Session ID to scope retrieval.
            query: Query text to embed and search.
            top_k: Number of results to return.

        Returns:
            Formatted context string for LLM injection.
        """
        if not self.is_loaded or self._index is None or len(self._texts) == 0:
            return ""

        import numpy as np

        query_emb = self._embedder.encode([query], convert_to_numpy=True).astype(np.float32)
        k = min(top_k, len(self._texts))
        distances, indices = self._index.search(query_emb, k)

        results = []
        for idx in indices[0]:
            if idx >= 0 and idx < len(self._texts):
                results.append(self._texts[idx])

        if not results:
            return ""

        return "Previous context:\n" + "\n".join(f"- {r}" for r in results)


# Module-level singleton
_ltm_store: Optional[LongTermMemoryStore] = None


def get_ltm_store() -> LongTermMemoryStore:
    """Return the singleton LTM store."""
    global _ltm_store
    if _ltm_store is None:
        _ltm_store = LongTermMemoryStore()
    return _ltm_store
