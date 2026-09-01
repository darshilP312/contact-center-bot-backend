# 🚀 InsureAI Command Center 3.0 — Backend

FastAPI asynchronous backend with real-time WebSockets, WebRTC, Enterprise Tools (CRM, Billing, Scheduling), and Hybrid RAG Knowledge Engine.

---

## ⚡ Quick Start

### 1. Install Dependencies
```bash
# Using standard pip
pip install -r requirements.txt

# Or using uv
uv sync
```

### 2. Configure Environment
Copy `.env.example` to `.env` and configure your database and API keys:
```bash
cp .env.example .env
```

### 3. Initialize & Seed Database
```bash
# 1. Create database tables
python init_db.py

# 2. Seed customers, billing plans, invoices, transactions & agents
python seed_master.py

# 3. Seed RAG knowledge base & verify retrieval
python seed_rag_kb.py --force
```

### 4. Run Verification Tests
```bash
# Verify authentication for all 10 pre-seeded users
python verify_logins.py

# Verify CRM, Billing, and Scheduling DB queries
python test_services.py
```

### 5. Start Backend Server
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- **Interactive API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## 🔑 Pre-Seeded Logins
- **Anita Desai** (`anita.desai@example.com` / `AnitaPass123!`) — Tier: Premium
- **Rajan Mehta** (`rajan.mehta@example.com` / `RajanPass123!`) — Tier: Premium
- **Priya Sharma** (`priya.sharma@example.com` / `PriyaPass123!`) — Tier: Gold
- **Suresh Kumar** (`suresh.kumar@example.com` / `SureshPass123!`) — Tier: Basic
*(Refer to the root [README.md](../README.md) for full accounts table and details.)*
