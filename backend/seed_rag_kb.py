"""
seed_rag_kb.py — Standalone RAG knowledge base seeder and retrieval tester.

Embeds all 19 KB files from app/orchestrator/rag/data/knowledge_base/ into:
  - ChromaDB (persistent vector store): app/orchestrator/rag/data/chroma_db/
  - FAISS index (built from ChromaDB embeddings, in-memory, rebuilt on startup)

Run this to force a full re-index and verify retrieval quality.

Usage:
    cd backend/
    uv run python seed_rag_kb.py            # init (skip if already indexed)
    uv run python seed_rag_kb.py --force    # clear + full re-embed all files
"""
from __future__ import annotations

import asyncio
import sys

# ─── Sample test queries and expected domains ──────────────────────────────────
SAMPLE_QUERIES = [
    # Motor
    ("What is zero depreciation cover and how does it help?", "motor_insurance"),
    ("How do I file a cashless motor claim at a network garage?", "motor_insurance"),
    ("What is NCB No Claim Bonus in car insurance?", "motor_insurance"),

    # Health — general
    ("What does Health Shield Gold cover for hospitalisation?", "health_insurance"),
    ("What is the room rent limit under Health Shield Gold plan?", "health_insurance"),
    ("How to file a reimbursement health insurance claim?", "health_insurance"),
    ("Does Health Shield Gold have zero copay?", "health_insurance"),
    ("What is the quarterly premium for Health Shield Gold?", "health_insurance"),

    # Health — Anita Desai scenario (new)
    ("Can Anita Desai claim her appendectomy surgery under Health Shield Gold?", "health_insurance"),
    ("What happens if Anita Desai goes to a non-network hospital?", "health_insurance"),
    ("Does Anita Desai have a waiting period for pre-existing conditions?", "health_insurance"),

    # Home
    ("What is covered under Home Protector Elite for earthquake damage?", "home_insurance"),
    ("How do I file a burglary claim in home insurance?", "home_insurance"),

    # General cross-domain
    ("What payment methods are accepted for premium payment?", None),
    ("How to port my health insurance to SecureShield?", None),
]


async def main():
    force_reload = "--force" in sys.argv

    print("=" * 62)
    print("  SecureShield RAG Knowledge Base Seeder")
    print("  Vector DB: app/orchestrator/rag/data/chroma_db/")
    print("  Knowledge: app/orchestrator/rag/data/knowledge_base/")
    print("=" * 62)

    # Import the singleton rag_engine from the integrated module
    from app.orchestrator.rag import rag_engine

    if force_reload:
        print("\n[FORCE RELOAD] Clearing ChromaDB and re-embedding all 19 KB files...")
        status = await rag_engine.reload_documents()
    else:
        print("\n[INIT] Initializing RAG engine (idempotent — skips if already indexed)...")
        status = await rag_engine.initialize()

    print("\n--- Seeding Results ---")
    print(f"  Documents loaded     : {status.get('documents_loaded', 0)}")
    print(f"  ChromaDB upserted    : {status.get('chromadb_upserted', 0)}")
    print(f"  ChromaDB status      : {status.get('chromadb', '?')}")
    print(f"  FAISS status         : {status.get('faiss', '?')}")
    print(f"  FAISS doc count      : {status.get('faiss_docs', 0)}")
    print(f"  Redis status         : {status.get('redis', '?')}")

    if not rag_engine.is_ready:
        print("\n[ERROR] RAG engine not ready. Check logs above.")
        return

    print("\n" + "=" * 62)
    print("  Running Retrieval Tests")
    print("=" * 62)

    passed = 0
    failed = 0

    for query, expected_domain in SAMPLE_QUERIES:
        results = await rag_engine.search(query=query, top_k=3, domain=expected_domain)

        if results:
            top = results[0]
            passed += 1
            domain_hit = top.domain or "N/A"
            score = round(top.score, 3)
            title = (top.section_title or "(no title)")[:55]
            print(f"\n[OK] {query[:62]}")
            print(f"     Domain: {domain_hit} | Score: {score}")
            print(f"     Top chunk: {title}")
            print(f"     Source: {top.source}")
        else:
            failed += 1
            print(f"\n[FAIL] {query[:62]}")
            print(f"       No results returned (domain_filter={expected_domain})")

    print("\n" + "=" * 62)
    print(f"  Test Results: {passed} passed, {failed} failed out of {len(SAMPLE_QUERIES)} queries")
    print("=" * 62)

    health = await rag_engine.health_check()
    print(f"\n  ChromaDB doc count   : {health['chromadb']['doc_count']}")
    print(f"  FAISS doc count      : {health['faiss']['doc_count']}")
    print(f"  Redis                : {health['redis']['status']}")
    print()

    await rag_engine.close()
    print("[DONE] RAG seeding and verification complete.")


if __name__ == "__main__":
    asyncio.run(main())
