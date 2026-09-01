"""
app.orchestrator.rag — Production-Grade RAG Engine

A fully integrated Retrieval-Augmented Generation engine using:
  - ChromaDB (persistent semantic vector store, HNSW cosine index)
  - FAISS (fast ANN index built on top of ChromaDB embeddings)
  - Redis (query result caching, graceful degradation if unavailable)
  - Reciprocal Rank Fusion (merges ChromaDB + FAISS results)

Knowledge base: app/orchestrator/rag/data/knowledge_base/
  - Motor insurance: 7 files (KB + policies)
  - Health insurance: 7 files (KB + policies)
  - Home insurance: 3 files (KB + policies)
  - General insurance: 1 file

Vector store: app/orchestrator/rag/data/chroma_db/

Usage:
    from app.orchestrator.rag import rag_engine

    # Initialize on app startup
    status = await rag_engine.initialize()

    # Search
    results = await rag_engine.search("What is zero depreciation?", top_k=5)

    # Health check
    health = await rag_engine.health_check()
"""

from app.orchestrator.rag.search_engine import RAGSearchEngine, RAGResult as RAGSearchResult
from app.orchestrator.rag.config import RAGConfig
from app.orchestrator.rag.manager import RAGManager, RAGResult, RetrievedPassage
from app.orchestrator.rag.embedder import TextEmbedder
from app.orchestrator.rag.seeder import seed_knowledge_base

# Global singleton — initialized once during lifespan, shared across all requests
rag_engine = RAGSearchEngine()

__all__ = [
    "rag_engine",
    "RAGSearchEngine",
    "RAGConfig",
    "RAGManager",
    "RAGResult",
    "RetrievedPassage",
    "TextEmbedder",
    "seed_knowledge_base",
]
