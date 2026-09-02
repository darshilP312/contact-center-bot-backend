"""
ChromaDB Persistent Vector Store

Manages document embeddings in a persistent ChromaDB collection with
sentence-transformers for symmetric semantic search. Thread-safe for
concurrent query handling.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .config import RAGConfig, rag_config
from .document_loader import KBChunk

logger = logging.getLogger("rag.vector_store")


class ChromaVectorStore:
    """
    Persistent ChromaDB vector store with sentence-transformers embeddings.

    - Uses ChromaDB's built-in SentenceTransformerEmbeddingFunction for symmetric search
    - Persistent storage survives application restarts
    - Thread-safe for concurrent queries (ChromaDB handles internal locking)
    - Supports metadata-filtered search by domain, doc_type, etc.
    """

    def __init__(self, config: Optional[RAGConfig] = None) -> None:
        self.config = config or rag_config
        self._client = None
        self._collection = None
        self._embedding_fn = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize ChromaDB client, embedding function, and collection."""
        import chromadb
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

        chroma_dir = Path(self.config.chroma_dir)
        chroma_dir.mkdir(parents=True, exist_ok=True)

        # Persistent client — data survives restarts
        self._client = chromadb.PersistentClient(path=str(chroma_dir))

        # Symmetric embedding function (same model for queries and documents)
        self._embedding_fn = SentenceTransformerEmbeddingFunction(
            model_name=self.config.embedding_model
        )

        # Get or create the collection
        self._collection = self._client.get_or_create_collection(
            name=self.config.chroma_collection_name,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"},  # Cosine similarity for symmetric search
        )

        self._initialized = True
        logger.info(
            f"ChromaDB initialized: collection='{self.config.chroma_collection_name}', "
            f"model='{self.config.embedding_model}', "
            f"existing_docs={self._collection.count()}"
        )

    def upsert_documents(self, chunks: List[KBChunk]) -> int:
        """
        Batch upsert chunks into ChromaDB with metadata.

        Returns:
            Number of documents upserted.
        """
        if not self._initialized:
            raise RuntimeError("ChromaVectorStore not initialized. Call initialize() first.")

        if not chunks:
            return 0

        # ChromaDB batch size limit
        batch_size = 500
        total = 0

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            ids = [c.id for c in batch]
            documents = [c.content for c in batch]
            metadatas = [
                {
                    "domain": c.domain,
                    "section_id": c.section_id,
                    "section_title": c.section_title,
                    "doc_type": c.doc_type,
                    "source_file": c.source_file,
                    "keywords": ",".join(c.keywords),
                }
                for c in batch
            ]

            self._collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
            )
            total += len(batch)

        logger.info(f"Upserted {total} chunks into ChromaDB")
        return total

    def search(
        self,
        query: str,
        top_k: int = 5,
        domain_filter: Optional[str] = None,
        doc_type_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search with optional metadata filtering.

        Args:
            query: The search query text
            top_k: Number of results to return
            domain_filter: Optional filter by domain (e.g., "motor_insurance")
            doc_type_filter: Optional filter by doc_type (e.g., "faq")

        Returns:
            List of dicts with 'id', 'content', 'metadata', 'score'
        """
        if not self._initialized:
            raise RuntimeError("ChromaVectorStore not initialized. Call initialize() first.")

        # Build where filter
        where_filter = None
        if domain_filter and doc_type_filter:
            where_filter = {
                "$and": [
                    {"domain": {"$eq": domain_filter}},
                    {"doc_type": {"$eq": doc_type_filter}},
                ]
            }
        elif domain_filter:
            where_filter = {"domain": {"$eq": domain_filter}}
        elif doc_type_filter:
            where_filter = {"doc_type": {"$eq": doc_type_filter}}

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=min(top_k, self._collection.count() or top_k),
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.error(f"ChromaDB search error: {e}")
            return []

        search_results = []
        if results and results["ids"] and results["ids"][0]:
            for idx, doc_id in enumerate(results["ids"][0]):
                # ChromaDB returns distances (lower = more similar for cosine)
                # Convert to similarity score: score = 1 - distance
                distance = results["distances"][0][idx] if results["distances"] else 0.0
                score = max(0.0, 1.0 - distance)

                search_results.append(
                    {
                        "id": doc_id,
                        "content": results["documents"][0][idx],
                        "metadata": results["metadatas"][0][idx] if results["metadatas"] else {},
                        "score": score,
                        "source": "chromadb",
                    }
                )

        return search_results

    def get_all_embeddings(self) -> Tuple[np.ndarray, List[str]]:
        """
        Retrieve all embeddings and their IDs from ChromaDB for FAISS index building.

        Returns:
            Tuple of (embeddings_array [N x dim], list_of_ids)
        """
        if not self._initialized:
            raise RuntimeError("ChromaVectorStore not initialized. Call initialize() first.")

        count = self._collection.count()
        if count == 0:
            return np.array([]).reshape(0, self.config.embedding_dimension), []

        result = self._collection.get(
            include=["embeddings"],
            limit=count,
        )

        ids = result["ids"]
        embeddings = np.array(result["embeddings"], dtype=np.float32)

        logger.info(f"Retrieved {len(ids)} embeddings from ChromaDB (shape: {embeddings.shape})")
        return embeddings, ids

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query text using the same model as documents."""
        if not self._initialized or self._embedding_fn is None:
            raise RuntimeError("ChromaVectorStore not initialized. Call initialize() first.")

        embedding = self._embedding_fn([query])
        return np.array(embedding, dtype=np.float32)

    def count(self) -> int:
        """Return the total number of documents in the collection."""
        if not self._initialized or self._collection is None:
            return 0
        return self._collection.count()

    def clear(self) -> None:
        """Delete all documents from the collection."""
        if self._initialized and self._client:
            try:
                self._client.delete_collection(self.config.chroma_collection_name)
                self._collection = self._client.get_or_create_collection(
                    name=self.config.chroma_collection_name,
                    embedding_function=self._embedding_fn,
                    metadata={"hnsw:space": "cosine"},
                )
                logger.info("ChromaDB collection cleared and recreated")
            except Exception as e:
                logger.error(f"Error clearing ChromaDB collection: {e}")

    def ping(self) -> bool:
        """Health check — verify ChromaDB is responsive."""
        try:
            if self._initialized and self._client:
                self._client.heartbeat()
                return True
        except Exception:
            pass
        return False
