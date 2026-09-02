"""
Document Loader & Smart Chunking Pipeline

Loads Markdown (.md), Text (.txt), and JSON knowledge base documents and splits them into
semantically meaningful chunks with hierarchical clause and section metadata for high-precision
vector search and retrieval.
"""

from __future__ import annotations

import json
import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import RAGConfig, rag_config

logger = logging.getLogger("rag.document_loader")


@dataclass
class KBChunk:
    """A single searchable chunk from a knowledge base document."""

    id: str                         # Unique chunk ID (hash-based)
    content: str                    # The searchable text content
    domain: str                     # e.g., "motor_insurance", "health_insurance", "telecom"
    section_id: str                 # Parent section identifier
    section_title: str              # Human-readable section title
    doc_type: str                   # "policy_clause" | "faq" | "section" | "paragraph"
    source_file: str                # Original filename
    keywords: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "domain": self.domain,
            "section_id": self.section_id,
            "section_title": self.section_title,
            "doc_type": self.doc_type,
            "source_file": self.source_file,
            "keywords": self.keywords,
            **self.metadata,
        }


class DocumentLoader:
    """
    Loads and chunks real-world Markdown policy wordings, Text files, and JSON documents.

    Chunking Strategy:
    - Markdown / Text Policy Docs: Splits by sections (`### SECTION`, `#### Clause`) preserving hierarchy.
    - Each clause text is chunked into ~500-char paragraphs with 50-char overlap.
    - JSON KB: Each FAQ & section is loaded with question/answer pairing.
    """

    def __init__(self, config: Optional[RAGConfig] = None) -> None:
        self.config = config or rag_config

    def load_all(self, kb_dir: Optional[str] = None) -> List[KBChunk]:
        """
        Scans the knowledge base directory for all *.md, *.txt, and *_kb.json files,
        loads and chunks each one.

        Returns:
            List of KBChunk objects ready for embedding.
        """
        directory = Path(kb_dir or self.config.kb_dir)
        if not directory.exists():
            logger.warning(f"Knowledge base directory not found: {directory}")
            return []

        all_chunks: List[KBChunk] = []
        seen_ids: set = set()

        # 1. Load Markdown & Text real-world policy documents (Primary)
        for doc_file in sorted(directory.glob("*.md")) + sorted(directory.glob("*.txt")):
            try:
                chunks = self._load_markdown_file(doc_file)
                for chunk in chunks:
                    if chunk.id not in seen_ids:
                        all_chunks.append(chunk)
                        seen_ids.add(chunk.id)
                logger.info(f"Loaded {len(chunks)} chunks from {doc_file.name}")
            except Exception as e:
                logger.error(f"Error loading {doc_file.name}: {e}", exc_info=True)

        # 2. Load JSON KB files if present
        for json_file in sorted(directory.glob("*_kb.json")):
            try:
                chunks = self._load_json_file(json_file)
                for chunk in chunks:
                    if chunk.id not in seen_ids:
                        all_chunks.append(chunk)
                        seen_ids.add(chunk.id)
                logger.info(f"Loaded {len(chunks)} chunks from {json_file.name}")
            except Exception as e:
                logger.error(f"Error loading {json_file.name}: {e}")

        logger.info(f"Total knowledge base chunks loaded: {len(all_chunks)}")
        return all_chunks

    def _infer_domain(self, file_stem: str) -> str:
        """Infer domain category from filename stem."""
        stem = file_stem.lower()
        if "motor" in stem or "car" in stem or "vehicle" in stem:
            return "motor_insurance"
        elif "health" in stem or "medical" in stem or "hospital" in stem:
            return "health_insurance"
        elif "telecom" in stem or "broadband" in stem or "internet" in stem or "billing" in stem:
            return "telecom"
        return stem.replace("_kb", "").replace("_policy_wording", "")

    def _load_markdown_file(self, file_path: Path) -> List[KBChunk]:
        """
        Parses a Markdown policy wording document into clause-level searchable chunks.
        Extracts headers (`#`, `##`, `###`, `####`) to maintain rich hierarchical context.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        domain = self._infer_domain(file_path.stem)
        source_file = file_path.name
        chunks: List[KBChunk] = []

        # Split document by markdown headings (H2, H3, H4) or major section breaks
        # Pattern matches headers like: ### SECTION I... or #### Clause 1.1...
        section_pattern = re.compile(r"(^(?:#{2,4}\s+|SECTION\s+|CLAUSE\s+)[^\n]+)", re.MULTILINE | re.IGNORECASE)
        splits = section_pattern.split(text)

        current_major_section = file_path.stem.replace("_", " ").title()
        current_sub_section = "General Terms"

        i = 0
        while i < len(splits):
            segment = splits[i].strip()
            if not segment:
                i += 1
                continue

            # Check if this segment is a header
            if section_pattern.match(segment):
                header_line = segment.lstrip("#").strip()
                if header_line.upper().startswith("SECTION") or "POLICY" in header_line.upper():
                    current_major_section = header_line
                    current_sub_section = header_line
                else:
                    current_sub_section = header_line
                i += 1
                if i < len(splits):
                    body_text = splits[i].strip()
                    i += 1
                else:
                    body_text = ""
            else:
                body_text = segment
                i += 1

            if not body_text:
                continue

            # Full contextual title for retrieval precision
            composite_title = f"{current_major_section} — {current_sub_section}" if current_sub_section != current_major_section else current_major_section
            section_id = re.sub(r"[^a-zA-Z0-9_]+", "_", current_sub_section.lower()).strip("_")[:40]

            # Split body into overlapping paragraphs
            body_chunks = self._chunk_text(
                text=body_text,
                domain=domain,
                section_id=section_id,
                section_title=composite_title,
                doc_type="policy_clause",
                source_file=source_file,
                keywords=self._extract_keywords(body_text),
            )
            chunks.extend(body_chunks)

        return chunks

    def _load_json_file(self, file_path: Path) -> List[KBChunk]:
        """Load a single KB JSON file and produce chunks."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        domain = data.get("domain", self._infer_domain(file_path.stem))
        source_file = file_path.name
        chunks: List[KBChunk] = []

        for section in data.get("sections", []):
            section_id = section.get("id", "unknown")
            section_title = section.get("title", "Untitled")
            section_content = section.get("content", "")
            keywords = section.get("keywords", [])

            # Section content chunk(s)
            if section_content:
                section_chunks = self._chunk_text(
                    text=section_content,
                    domain=domain,
                    section_id=section_id,
                    section_title=section_title,
                    doc_type="section",
                    source_file=source_file,
                    keywords=keywords,
                )
                chunks.extend(section_chunks)

            # FAQ chunks
            for j, faq in enumerate(section.get("faqs", [])):
                question = faq.get("question", "")
                answer = faq.get("answer", "")
                if question and answer:
                    faq_content = f"Question: {question}\nAnswer: {answer}"
                    faq_id = self._make_id(domain, section_id, f"faq_{j}", faq_content)
                    chunks.append(
                        KBChunk(
                            id=faq_id,
                            content=faq_content,
                            domain=domain,
                            section_id=section_id,
                            section_title=section_title,
                            doc_type="faq",
                            source_file=source_file,
                            keywords=keywords,
                            metadata={"question": question},
                        )
                    )

        return chunks

    def _chunk_text(
        self,
        text: str,
        domain: str,
        section_id: str,
        section_title: str,
        doc_type: str,
        source_file: str,
        keywords: List[str],
    ) -> List[KBChunk]:
        """
        Split text into chunks of configurable size with overlap.
        Short texts (< chunk_size) are kept as a single chunk with full section context.
        """
        chunk_size = self.config.chunk_size
        chunk_overlap = self.config.chunk_overlap
        chunks: List[KBChunk] = []

        # Prefix with section context for dense vector semantics
        context_prefix = f"[{section_title}]\n"

        if len(text) <= chunk_size:
            chunk_content = f"{context_prefix}{text}"
            chunk_id = self._make_id(domain, section_id, doc_type, chunk_content)
            chunks.append(
                KBChunk(
                    id=chunk_id,
                    content=chunk_content,
                    domain=domain,
                    section_id=section_id,
                    section_title=section_title,
                    doc_type=doc_type,
                    source_file=source_file,
                    keywords=keywords,
                )
            )
        else:
            start = 0
            part_idx = 0
            while start < len(text):
                end = min(start + chunk_size, len(text))
                # Break on a sentence boundary
                if end < len(text):
                    last_period = max(text.rfind(". ", start, end), text.rfind("\n", start, end))
                    if last_period > start + chunk_size // 2:
                        end = last_period + 1

                chunk_slice = text[start:end].strip()
                if chunk_slice:
                    chunk_content = f"{context_prefix}{chunk_slice}"
                    chunk_id = self._make_id(domain, section_id, f"{doc_type}_p{part_idx}", chunk_content)
                    chunks.append(
                        KBChunk(
                            id=chunk_id,
                            content=chunk_content,
                            domain=domain,
                            section_id=section_id,
                            section_title=section_title,
                            doc_type="paragraph" if doc_type != "policy_clause" else "policy_clause",
                            source_file=source_file,
                            keywords=keywords,
                            metadata={"part_index": part_idx},
                        )
                    )
                    part_idx += 1

                start = end - chunk_overlap if end < len(text) else len(text)

        return chunks

    @staticmethod
    def _extract_keywords(text: str) -> List[str]:
        """Extract core keywords from text."""
        words = re.findall(r"\b[A-Za-z0-9_-]{4,}\b", text.lower())
        stopwords = {"this", "that", "with", "from", "shall", "will", "under", "which", "after", "before", "their", "there", "about", "other"}
        return [w for w in set(words) if w not in stopwords][:10]

    @staticmethod
    def _make_id(domain: str, section_id: str, suffix: str, content: str) -> str:
        """Generate a deterministic, unique chunk ID."""
        raw = f"{domain}::{section_id}::{suffix}::{content[:120]}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
