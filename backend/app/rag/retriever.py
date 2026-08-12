"""
retriever.py — FAISS-backed similarity search with source citations.
Provides the retrieve() function used by the execute node.
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Optional

import numpy as np
import faiss
from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger("cc.rag")

INDEX_PATH = Path(__file__).parent / "faiss_index.pkl"
client = AsyncOpenAI(api_key=settings.openai_api_key)


class RAGRetriever:
    """FAISS-backed retriever with embedding query and citation support."""

    def __init__(self) -> None:
        self.index: Optional[faiss.Index] = None
        self.chunks: list[dict] = []
        self._loaded = False
        self._try_load()

    def _try_load(self) -> None:
        """Attempt to load the pre-built FAISS index."""
        if not INDEX_PATH.exists():
            logger.warning(
                f"FAISS index not found at {INDEX_PATH}. "
                "Run: python -m app.rag.indexer"
            )
            return

        with open(INDEX_PATH, "rb") as f:
            data = pickle.load(f)

        self.index = data["index"]
        self.chunks = data["chunks"]
        self._loaded = True
        logger.info(f"FAISS index loaded: {len(self.chunks)} chunks.")

    async def retrieve(self, query: str, top_k: int = 3) -> dict:
        """
        Embed query and retrieve top-k similar policy chunks.

        Returns:
            dict with keys: chunks (list of {text, source, score}), query
        """
        if not self._loaded or not self.chunks:
            return {
                "chunks": [],
                "query": query,
                "error": "RAG index not loaded. Run python -m app.rag.indexer first.",
            }

        # Embed query
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=query,
        )
        query_vec = np.array([response.data[0].embedding], dtype="float32")
        faiss.normalize_L2(query_vec)

        # Search
        distances, indices = self.index.search(query_vec, top_k)

        results = []
        for score, idx in zip(distances[0], indices[0]):
            if 0 <= idx < len(self.chunks):
                results.append({
                    "text": self.chunks[idx]["text"],
                    "source": self.chunks[idx]["source"],
                    "chunk_id": self.chunks[idx]["chunk_id"],
                    "score": float(score),
                })

        return {
            "chunks": results,
            "query": query,
            "retrieved_count": len(results),
        }


# ── Module-level singleton ─────────────────────────────────────────────────────

_retriever = RAGRetriever()


async def retrieve(query: str, top_k: int = 3) -> dict:
    """Public API for the execute node."""
    return await _retriever.retrieve(query, top_k)
