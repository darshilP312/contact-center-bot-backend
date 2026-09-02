"""
RAG Module — Production-Grade Retrieval-Augmented Generation Engine

A self-contained, reusable RAG module using ChromaDB + FAISS + Redis.
Designed for high-concurrency (30-40+ concurrent queries), symmetric semantic search,
and graceful degradation.

Usage:
    from RAG import rag_engine

    # Initialize on app startup
    await rag_engine.initialize()

    # Search
    results = await rag_engine.search("What is zero depreciation?", top_k=5)

    # Health check
    status = await rag_engine.health_check()
"""

from .search_engine import RAGSearchEngine, RAGResult
from .config import RAGConfig

# Global singleton — initialized once, shared across the application
rag_engine = RAGSearchEngine()

__all__ = [
    "rag_engine",
    "RAGSearchEngine",
    "RAGResult",
    "RAGConfig",
]
