"""
indexer.py — Build the FAISS vector index from policy corpus documents.
Run once before starting the server: python -m app.rag.indexer
"""

from __future__ import annotations

import os
import pickle
from pathlib import Path

import numpy as np
import faiss
from openai import OpenAI

from app.config import settings

CORPUS_DIR = Path(__file__).parent / "corpus"
INDEX_PATH = Path(__file__).parent / "faiss_index.pkl"
CHUNK_SIZE = 400   # characters per chunk
CHUNK_OVERLAP = 80 # overlap between chunks

client = OpenAI(api_key=settings.openai_api_key)


def chunk_text(text: str, source: str) -> list[dict]:
    """Split text into overlapping chunks for indexing."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk_text_content = text[start:end].strip()
        if chunk_text_content:
            chunks.append({
                "text": chunk_text_content,
                "source": source,
                "chunk_id": len(chunks),
            })
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def build_index() -> None:
    """
    Read all .txt files from the corpus directory,
    chunk them, embed them, and store in a FAISS flat IP index.
    """
    print(f"Loading corpus from {CORPUS_DIR}...")
    all_chunks = []

    for txt_file in sorted(CORPUS_DIR.glob("*.txt")):
        text = txt_file.read_text(encoding="utf-8")
        chunks = chunk_text(text, txt_file.name)
        all_chunks.extend(chunks)
        print(f"  {txt_file.name}: {len(chunks)} chunks")

    print(f"\nEmbedding {len(all_chunks)} chunks...")
    texts = [c["text"] for c in all_chunks]

    # Embed in batches of 100
    all_embeddings = []
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=batch,
        )
        for item in response.data:
            all_embeddings.append(item.embedding)
        print(f"  Embedded batch {i // batch_size + 1}/{(len(texts) + batch_size - 1) // batch_size}")

    # Build FAISS index (Inner Product with normalised vectors = cosine similarity)
    dim = len(all_embeddings[0])
    index = faiss.IndexFlatIP(dim)

    vectors = np.array(all_embeddings, dtype="float32")
    faiss.normalize_L2(vectors)
    index.add(vectors)

    # Persist
    with open(INDEX_PATH, "wb") as f:
        pickle.dump({"index": index, "chunks": all_chunks}, f)

    print(f"\nIndex saved to {INDEX_PATH}")
    print(f"Total chunks indexed: {len(all_chunks)}")
    print(f"Vector dimension: {dim}")


if __name__ == "__main__":
    build_index()
