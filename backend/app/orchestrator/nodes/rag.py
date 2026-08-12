from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("orchestrator.rag")
settings = get_settings()

# Text splitting parameters
CHUNK_SIZE = 512
CHUNK_OVERLAP = 64


def _split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks by character count."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


class RAGNode:
    """
    RAG (Retrieval-Augmented Generation) Node.

    Builds a FAISS index per domain from knowledge documents at startup.
    On query, embeds the question and retrieves top-k relevant chunks.

    Supports: FAISS (default dev) / pgvector (production via env var).
    """

    def __init__(self, domain_loader: Any) -> None:
        self.domain_loader = domain_loader
        self._indices: Dict[str, Any] = {}      # domain_id -> faiss.IndexFlatL2
        self._texts: Dict[str, List[str]] = {}  # domain_id -> list of chunks
        self._sources: Dict[str, List[str]] = {} # domain_id -> source file per chunk
        self._embedder: Any = None

    async def _load_embedder(self) -> None:
        """Load sentence-transformers embedding model."""
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer(settings.EMBEDDING_MODEL)
            logger.info("RAG embedder loaded", node="orchestrator.rag", model=settings.EMBEDDING_MODEL)

    async def build_all_indices(self) -> None:
        """Build FAISS indices for all loaded domains."""
        await self._load_embedder()

        for domain_id in self.domain_loader.domains:
            await self._build_domain_index(domain_id)

    async def _build_domain_index(self, domain_id: str) -> None:
        """Build a FAISS index for a single domain's knowledge documents."""
        import faiss

        knowledge_dir = self.domain_loader.get_knowledge_dir(domain_id)
        if not knowledge_dir or not os.path.isdir(knowledge_dir):
            logger.debug(
                "No knowledge dir for domain",
                node="orchestrator.rag",
                domain_id=domain_id,
            )
            return

        all_chunks = []
        all_sources = []

        knowledge_path = Path(knowledge_dir)
        supported_files = sorted(list(knowledge_path.glob("*.md")) + list(knowledge_path.glob("*.txt")) + list(knowledge_path.glob("*.pdf")))

        for doc_file in supported_files:
            try:
                text = ""
                if doc_file.suffix.lower() == ".pdf":
                    try:
                        import pypdf
                        reader = pypdf.PdfReader(str(doc_file))
                        pages_text = [page.extract_text() or "" for page in reader.pages]
                        text = "\n".join(pages_text)
                    except Exception as pdf_err:
                        logger.warning(
                            "pypdf extraction failed, attempting fitz",
                            node="orchestrator.rag",
                            file=str(doc_file),
                            error=str(pdf_err),
                        )
                        import fitz
                        doc = fitz.open(str(doc_file))
                        text = "\n".join([page.get_text() for page in doc])
                else:
                    text = doc_file.read_text(encoding="utf-8")

                if text.strip():
                    chunks = _split_text(text)
                    all_chunks.extend(chunks)
                    all_sources.extend([doc_file.name] * len(chunks))
            except Exception as e:
                logger.warning(
                    "Failed to read knowledge doc",
                    node="orchestrator.rag",
                    file=str(doc_file),
                    error=str(e),
                )

        if not all_chunks:
            return

        # Embed all chunks
        embeddings = self._embedder.encode(all_chunks, convert_to_numpy=True).astype(np.float32)

        # Build FAISS index
        dim = embeddings.shape[1]
        index = faiss.IndexFlatL2(dim)
        index.add(embeddings)

        self._indices[domain_id] = index
        self._texts[domain_id] = all_chunks
        self._sources[domain_id] = all_sources

        logger.info(
            "RAG index built",
            node="orchestrator.rag",
            domain_id=domain_id,
            chunks=len(all_chunks),
            sources=list(set(all_sources)),
        )

    async def retrieve(
        self,
        domain_id: str,
        query: str,
        top_k: Optional[int] = None,
    ) -> tuple[str, List[str]]:
        """
        Retrieve top-k relevant chunks for a query in a domain's knowledge base.

        Args:
            domain_id: Domain to search.
            query: Search query (customer's question).
            top_k: Number of chunks to retrieve.

        Returns:
            Tuple of (formatted_context_string, list_of_source_citations).
        """
        await self._load_embedder()
        k = top_k or settings.RAG_TOP_K

        if domain_id not in self._indices:
            return "", []

        index = self._indices[domain_id]
        texts = self._texts[domain_id]
        sources = self._sources[domain_id]

        if not texts:
            return "", []

        # Embed query
        query_emb = self._embedder.encode([query], convert_to_numpy=True).astype(np.float32)

        # Search
        k = min(k, len(texts))
        distances, indices = index.search(query_emb, k)

        retrieved_texts = []
        citations = []
        for idx in indices[0]:
            if 0 <= idx < len(texts):
                retrieved_texts.append(texts[idx])
                citations.append(sources[idx])

        context = "\n\n---\n\n".join(retrieved_texts) if retrieved_texts else ""
        unique_citations = list(dict.fromkeys(citations))  # Preserve order, deduplicate

        logger.info(
            "RAG retrieval complete",
            node="orchestrator.rag",
            domain_id=domain_id,
            query=query[:50],
            chunks_retrieved=len(retrieved_texts),
            citations=unique_citations,
        )

        return context, unique_citations


async def rag_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    RAG Node — triggered when requires_rag=True.

    Embeds the customer's query, retrieves top-k chunks from the domain's
    FAISS index, and stores results in state.rag_result and state.rag_citations.
    """
    session_id = state.get("session_id", "none")
    ws = state.get("_ws_connection")
    rag = state.get("_rag_node")
    domain = state.get("domain", "insurance")
    transcript = state.get("pii_masked_transcript", state.get("raw_transcript", ""))

    if ws:
        await ws.send_json("agent.thinking", {"node": "rag", "status": "running"})

    if not rag:
        logger.warning("RAG node not available", session_id=session_id, node="rag")
        return state

    try:
        context, citations = await rag.retrieve(domain_id=domain, query=transcript)
        state["rag_result"] = context
        state["rag_citations"] = citations

        flags = state.get("flags")
        if flags and context:
            flags.rag_used = True

        # Advance workflow step if active workflow includes RAG
        workflow = state.get("workflow")
        domain_loader = state.get("_domain_loader")
        if workflow and workflow.name:
            workflow_config = domain_loader.get_workflow(domain, workflow.name) if domain_loader else None
            steps = workflow_config.get("steps", []) if workflow_config else []
            total_steps = len(steps)

            current_step_id = workflow.step
            if current_step_id and current_step_id not in workflow.completed_steps:
                workflow.completed_steps.append(current_step_id)

            # Find next step
            next_step = None
            intent = state.get("intent")
            entities = intent.entities if intent else {}
            has_policy_no = bool(entities.get("policy_number"))

            if steps:
                completed_set = set(workflow.completed_steps)
                for step in steps:
                    if step["id"] not in completed_set:
                        if step["id"] == "lookup_specific_policy" and not has_policy_no:
                            workflow.completed_steps.append(step["id"])
                            continue
                        next_step = step["id"]
                        break

            workflow.step = next_step

            if ws:
                workflow_name = (workflow_config or {}).get("workflow_name", workflow.name) if workflow_config else workflow.name
                await ws.send_json(
                    "workflow.update",
                    {
                        "workflow_name": workflow_name,
                        "current_step": next_step,
                        "completed_steps": workflow.completed_steps,
                        "total_steps": total_steps,
                        "session_id": session_id,
                        "step_complete": True,
                    },
                )

        logger.info(
            "RAG context retrieved",
            session_id=session_id,
            node="rag",
            context_length=len(context),
            citations=citations,
        )
    except Exception as e:
        logger.error("RAG retrieval failed", session_id=session_id, node="rag", error=str(e))
        state["rag_result"] = ""
        state["rag_citations"] = []

    return state
