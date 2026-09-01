# 🛡️ InsureAI Command Center 3.0

> **Next-Generation AI-First Voice & Multimodal Contact Center with Real-Time WebSockets/WebRTC, Hybrid RAG Knowledge Engine, Autonomous Enterprise Tool Orchestration, and Supervisor Command Center.**

---

## 📋 Table of Contents
1. [Overview](#-overview)
2. [System Architecture](#-system-architecture)
3. [Key Features](#-key-features)
4. [Tech Stack](#-tech-stack)
5. [Prerequisites](#-prerequisites)
6. [Step-by-Step Setup & Installation](#-step-by-step-setup--installation)
   - [1. Database Configuration (PostgreSQL)](#1-database-configuration-postgresql)
   - [2. In-Memory Cache (Redis)](#2-in-memory-cache-redis)
   - [3. Backend Setup & Environment Variables](#3-backend-setup--environment-variables)
   - [4. Database Initialization & Seeding](#4-database-initialization--seeding)
   - [5. RAG Knowledge Base Seeding](#5-rag-knowledge-base-seeding)
   - [6. Frontend Setup](#6-frontend-setup)
7. [Running the Application](#-running-the-application)
8. [Sample User Accounts & Credentials](#-sample-user-accounts--credentials)
9. [How It Works & First Run Verification](#-how-it-works--first-run-verification)
   - [A. Policyholder Portal & Authentication](#a-policyholder-portal--authentication)
   - [B. Voice & Text AI Conversational Scenarios](#b-voice--text-ai-conversational-scenarios)
   - [C. Automated Service & RAG Test Scripts](#c-automated-service--rag-test-scripts)
   - [D. Real-time Supervisor Console](#d-real-time-supervisor-console)
10. [Repository Structure](#-repository-structure)
11. [Environment Variables Reference](#-environment-variables-reference)
12. [Troubleshooting](#-troubleshooting)

---

## 🌟 Overview

**InsureAI Command Center 3.0** is an enterprise-grade AI contact center platform designed for insurance operations (Health, Motor, and Home insurance). It blends real-time sub-second conversational voice AI with deep enterprise back-office integrations (CRM, Billing, Scheduling) and domain-aware retrieval-augmented generation (RAG).

```
   ┌───────────────────────────────────────────────────────────────┐
   │                     CUSTOMER FRONTEND                         │
   │           React 18 + TypeScript + Vite + WebRTC/WS            │
   └───────────────────────────────┬───────────────────────────────┘
                                   │ Real-time Audio / Text Stream
                                   ▼
   ┌───────────────────────────────────────────────────────────────┐
   │                   FASTAPI GATEWAY & ROUTER                    │
   │  Session Management · Audio Routing · Event Bus · Auth / JWT  │
   └───────────────────────────────┬───────────────────────────────┘
                                   │
         ┌─────────────────────────┴─────────────────────────┐
         ▼                                                   ▼
┌───────────────────────────────┐           ┌───────────────────────────────┐
│     AI AGENT ORCHESTRATOR     │           │   HYBRID RAG RETRIEVAL ENGINE │
│ • State & Turn Management     │           │ • 19 Insurance Knowledge Bases │
│ • Groq LLM Reasoning          │◄─────────►│ • ChromaDB Vector Store       │
│ • Tool Calling Engine         │           │ • FAISS In-Memory Index       │
│ • Edge TTS / Sarvam Audio     │           │ • Redis Semantic Caching      │
└───────────────┬───────────────┘           └───────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────────────┐
│                      ENTERPRISE SERVICES                          │
│   • CRM Service: Customer Profiles, Account Tier, History         │
│   • Billing Service: Invoices, Payments, Auto/Escalated Refunds   │
│   • Scheduling Service: On-site Damage Surveys, Consultations     │
│   • Database: PostgreSQL (Async SQLAlchemy) + Redis Cache         │
└───────────────────────────────────────────────────────────────────┘
```

---

## ✨ Key Features

- **⚡ Real-Time Voice & Text Streaming**: Sub-second latency turn-taking, barge-in / interruption detection, Edge-TTS streaming audio synthesis, and fallback STT support.
- **🧠 Domain-Aware Hybrid RAG**: Dual-tier vector retrieval using **ChromaDB** (persistent store) and **FAISS** (in-memory speed) with **Redis caching** across 19 policy documents (Health Shield, Motor Comprehensive, Home Protector, General insurance).
- **💼 Enterprise Tool Orchestration**:
  - **CRM**: Instant policyholder profile retrieval, coverage verification, tier classification.
  - **Billing**: Real-time invoice lookups, payment processing, smart refund evaluation with auto-approval threshold rules (≤ ₹5,000 auto-approved, > ₹5,000 supervisor escalation).
  - **Scheduling**: Real-time slot availability checking and surveyor/agent appointment booking.
- **🛡️ Multi-Role Security & Auth**: JWT-based authentication for policyholders and agents with bcrypt password hashing.
- **📊 Real-Time Supervisor Command Center**: Live call stream monitoring, real-time agent latency metrics, customer sentiment, and CSAT telemetry.

---

## 🛠️ Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | React 18, TypeScript, Vite, Zustand, Tailwind/Custom CSS, WebRTC, HTML5 Audio |
| **Backend API** | Python 3.11+, FastAPI, Uvicorn, WebSockets, Pydantic v2 |
| **Database & Cache** | PostgreSQL 15+ (asyncpg, SQLAlchemy 2.0 Async), Redis 6+ (aioredis) |
| **RAG & Vector Search** | ChromaDB, FAISS-CPU, Sentence-Transformers (`all-MiniLM-L6-v2`), LangChain Splitters |
| **AI / Voice Services** | Groq (`groq/compound-mini`), Sarvam AI, Microsoft Edge-TTS |
| **Authentication** | OAuth2 Password Bearer, JWT (`python-jose`), Passlib (`bcrypt`) |

---

## 📦 Prerequisites

Before starting, ensure you have the following installed on your machine:

1. **Python 3.11+** (`python --version`)
2. **Node.js 18+** & **npm** (`node -v`, `npm -v`)
3. **PostgreSQL 15+** running locally or via Docker
4. **Redis 6+** running locally (port 6379) or via Docker
5. *(Optional)* **Groq API Key** and **Sarvam AI API Key** for production LLM & Speech services (the system includes intelligent local/mock fallbacks if keys are not set).

---

## 🚀 Step-by-Step Setup & Installation

### 1. Database Configuration (PostgreSQL)

Open your PostgreSQL terminal (`psql`) or database GUI (such as pgAdmin or DBeaver) and create the database:

```sql
CREATE DATABASE command_center;
```

Ensure your PostgreSQL credentials match your environment settings (default user: `postgres`, password: `postgres`, host: `localhost:5432`).

---

### 2. In-Memory Cache (Redis)

Start your local Redis instance:

```bash
# On Linux / macOS:
redis-server

# On Windows (via WSL or Redis native service):
redis-server.exe

# Or with Docker:
docker run -d --name command-center-redis -p 6379:6379 redis:alpine
```

---

### 3. Backend Setup & Environment Variables

Navigate to the `backend/` directory:

```bash
cd backend
```

Create a virtual environment and activate it:

```bash
# Using Python venv:
python -m venv .venv

# On Windows:
.venv\Scripts\activate

# On Linux / macOS:
source .venv/bin/activate
```

Install backend dependencies:

```bash
pip install -r requirements.txt
# OR if using uv:
# uv sync
```

Create a `.env` file in the `backend/` directory (or copy from `.env.example`):

```env
# Database & Cache
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/command_center
REDIS_URL=redis://localhost:6379/0

# Authentication & Security
SECRET_KEY=command_center_super_secret_jwt_key_2026_change_in_prod
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS & Server
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000

# AI & Voice Providers (Optional - Mock fallbacks available)
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=groq/compound-mini
SARVAM_API_KEY=your_sarvam_api_key_here

# Business Rules
REFUND_THRESHOLD_AMOUNT=5000.0
REFUND_CURRENCY=INR
```

---

### 4. Database Initialization & Seeding

Initialize the schema tables and seed the database with all 10 policyholder accounts, invoices, billing transactions, service types, and agents:

```bash
# 1. Initialize DB tables
python init_db.py

# 2. Seed master data (customers, accounts, billing, appointments)
python seed_master.py
```

Output:
```
==================================================
>> Starting Master Database Seeder
==================================================
[OK] Database tables created/verified
--- Seeding Billing Plans ---
  + Billing Plan: Health Shield Gold (Rs.7499.0)
  + Billing Plan: Home Protector Elite (Rs.8499.0)
...
--- Seeding Policyholders & Logins ---
  + Customer: Anita Desai (anita.desai@example.com) -> Password: AnitaPass123!
  + Customer: Rajan Mehta (rajan.mehta@example.com) -> Password: RajanPass123!
...
[SUCCESS] Master Seeding Complete!
```

---

### 5. RAG Knowledge Base Seeding

Populate the RAG vector store with all 19 insurance policy manuals (Health, Motor, Home, General) into **ChromaDB** and initialize the **FAISS** index:

```bash
python seed_rag_kb.py --force
```

This will embed all policy documents and automatically run **14 test retrieval queries** to verify search accuracy and score rankings.

---

### 6. Frontend Setup

Open a new terminal window, navigate to the `frontend/` directory, and install dependencies:

```bash
cd frontend
npm install
```

---

## 🏃 Running the Application

### Start the Backend Server

From the `backend/` directory with your virtual environment activated:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
- **Backend API**: `http://localhost:8000`
- **Swagger API Docs**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/health`

### Start the Frontend Dev Server

From the `frontend/` directory:

```bash
npm run dev
```
- **Web Application**: `http://localhost:5173`

---

## 👥 Sample User Accounts & Credentials

The database is pre-seeded with 10 policyholder accounts spanning different tiers, plans, and cities for testing:

| # | Policyholder Name | Email Address | Password | Account No. | Plan Assigned | Tier |
| :- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | **Anita Desai** | `anita.desai@example.com` | `AnitaPass123!` | `ACC-003` | Home Protector Elite | Premium |
| 2 | **Rajan Mehta** | `rajan.mehta@example.com` | `RajanPass123!` | `ACC-002` | Health Shield Premium | Premium |
| 3 | **Suresh Kumar** | `suresh.kumar@example.com` | `SureshPass123!` | `ACC-004` | Motor Third Party | Basic |
| 4 | **Kavitha Nair** | `kavitha.nair@example.com` | `KavithaPass123!` | `ACC-005` | Health Shield Gold | Gold |
| 5 | **Priya Sharma** | `priya.sharma@example.com` | `PriyaPass123!` | `ACC-001` | Health Shield Gold | Gold |
| 6 | **Amit Patel** | `amit.patel@email.com` | `AmitPass123!` | `ACC-006` | Health Shield Basic | Basic |
| 7 | **Priya Nair** | `priya.nair@email.com` | `PriyaPass123!` | `ACC-007` | Motor Comprehensive | Gold |
| 8 | **Rahul Sharma** | `rahul.sharma@email.com` | `RahulPass123!` | `ACC-008` | Home Protector Basic | Basic |
| 9 | **Sneha Reddy** | `sneha.reddy@email.com` | `SnehaPass123!` | `ACC-009` | Motor Comprehensive Plus | Basic |
| 10 | **Vikram Singh** | `vikram.singh@email.com` | `VikramPass123!` | `ACC-010` | Motor Comprehensive | Gold |

### Pre-Configured Human Agents

| Agent Code | Agent Name | Department | Role | Specializations |
| :--- | :--- | :--- | :--- | :--- |
| `AGT-101` | **Rohan Sharma** | Claims | Senior Surveyor | Motor & Home Claims |
| `AGT-102` | **Ananya Sen** | Policy | Policy Specialist | Health Insurance & Tax Benefits |
| `AGT-103` | **Deepak Verma** | Billing | Billing Supervisor | Refunds, Disputes & GST |

---

## 🧪 How It Works & First Run Verification

Follow these steps to verify that every component is operating properly:

### A. Policyholder Portal & Authentication

1. Open `http://localhost:5173` in your browser.
2. Select any pre-configured user (e.g. **Anita Desai** or **Rajan Mehta**) from the fast-login pills or enter their credentials.
3. Click **Sign In**.
4. You will be directed to the Policyholder Portal displaying active coverage, upcoming renewals, outstanding invoices, and billing history.

---

### B. Voice & Text AI Conversational Scenarios

Click **"Start AI Consultation"** or switch to the Voice / Text Assistant:

#### 1. Policy & Coverage Inquiries (RAG Verification)
- **Prompt**: *"What is the room rent limit under my Health Shield Gold plan?"*
  - **AI Response**: Retrieves exact policy terms: *No sub-limit on room rent for single private AC rooms under Health Shield Gold.*
- **Prompt**: *"How do I file a cashless claim at a network garage for my car?"*
  - **AI Response**: Cites Motor Comprehensive claim steps: *Intimate insurer within 24h, provide policy number & FIR if required, vehicle surveyed on-site.*

#### 2. Account & Billing Inquiries (CRM + Billing Tool Verification)
- **Prompt**: *"Can you check my current pending invoice and due date?"*
  - **AI Action**: Calls `get_invoice(customer_id=...)` -> Reports exact pending amount, invoice number (`INV-2026-xxxx`), and due date.

#### 3. Refund & Dispute Management (Threshold Rule Verification)
- **Prompt (Auto-Approval)**: *"I was charged ₹1,200 twice for renewal fees. Can I get a refund?"*
  - **AI Action**: Evaluates amount (₹1,200 ≤ ₹5,000 threshold) -> Auto-approves refund -> Generates Refund ID `REF-2026-xxxx`.
- **Prompt (Supervisor Escalation)**: *"I want a refund of ₹15,000 for an erroneous policy debit."*
  - **AI Action**: Detects amount (₹15,000 > ₹5,000 threshold) -> Flags for human supervisor review with 48h SLA.

#### 4. Surveyor & Consultation Scheduling (Scheduling Tool Verification)
- **Prompt**: *"I need to book an engineer for a property damage inspection."*
  - **AI Action**: Calls `check_availability()` -> Suggests next available slots -> Books appointment with Agent **Rohan Sharma** (`APT-2026-xxxx`).

---

### C. Automated Service & RAG Test Scripts

You can run automated test scripts in `backend/` to verify each layer directly:

```bash
# 1. Test all 10 user logins against the Auth API
python verify_logins.py

# 2. Test CRM, Billing, and Scheduling DB services
python test_services.py

# 3. Test RAG knowledge base search & similarity scoring
python seed_rag_kb.py
```

---

### D. Real-Time Supervisor Console

1. Navigate to the **Supervisor Command Center** tab in the frontend.
2. Watch live WebSocket telemetry:
   - **Active Sessions Counter**: Current calls connected.
   - **Latency Breakdown**: End-to-end response time, STT duration, LLM token generation, and TTS synthesis.
   - **Real-Time Transcripts**: Live customer vs. AI dialogue stream.
   - **Supervisor Interventions**: Ability to monitor, whisper, or take over calls.

---

## 📁 Repository Structure

```
COMMAND_CENTER/
├── backend/
│   ├── app/
│   │   ├── api/                    # REST routes (auth, billing, crm, scheduling, analytics)
│   │   │   └── websocket/          # WebSocket audio, events, and supervisor broadcast
│   │   ├── core/                   # App settings, config, security & JWT utilities
│   │   ├── database/               # PostgreSQL async engine, session factory, Redis client
│   │   ├── enterprise/             # Enterprise business logic (CRM, Billing, Scheduling)
│   │   ├── gateway/                # Audio streaming router, session manager, WebRTC
│   │   ├── models/                 # SQLAlchemy ORM models (Customer, Invoice, Appointment, etc.)
│   │   ├── observability/          # Event bus, metrics, telemetry logger
│   │   ├── orchestrator/           # Agent orchestration, intent parser, LLM planner
│   │   │   └── rag/                # Hybrid RAG module (ChromaDB + FAISS + Redis Cache)
│   │   │       ├── data/
│   │   │       │   └── knowledge_base/ # 19 Insurance policy manuals & KB documents
│   │   │       ├── cache.py        # Redis semantic query cache
│   │   │       ├── document_loader.py # Markdown & JSON loaders
│   │   │       ├── faiss_index.py  # In-memory FAISS similarity index
│   │   │       ├── search_engine.py# Hybrid search orchestrator
│   │   │       ├── seeder.py       # Knowledge base seeder
│   │   │       └── vector_store.py # ChromaDB vector store client
│   │   ├── speech/                 # STT / TTS providers (Edge-TTS, Sarvam AI)
│   │   └── webrtc/                 # WebRTC peer connection & audio track handlers
│   ├── init_db.py                  # Schema table generator
│   ├── seed_master.py              # Master seeder for customers, billing & appointments
│   ├── seed_rag_kb.py              # Standalone RAG seeder & verification suite
│   ├── verify_logins.py            # Automated authentication test runner
│   ├── test_services.py            # Enterprise DB services functional test
│   ├── requirements.txt            # Python dependencies
│   └── main.py                     # FastAPI application entrypoint & lifespans
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── auth/               # Policyholder login & fast-switch credentials
│   │   │   ├── billing/            # Invoices, transactions, payment modal
│   │   │   ├── command-center/     # Supervisor monitoring console & telemetry
│   │   │   ├── conversation/       # Voice / text chat interface & audio visualizer
│   │   │   ├── crm/                # Policyholder details & tier cards
│   │   │   ├── scheduling/         # Appointment booking modal & slot picker
│   │   │   └── shared/             # Reusable UI primitives & badges
│   │   ├── contexts/               # React contexts (AuthContext, WebSocketContext)
│   │   ├── hooks/                  # Audio recording, WebRTC, and event hooks
│   │   ├── store/                  # Zustand state stores
│   │   ├── App.tsx                 # Main layout & route controller
│   │   └── main.tsx                # React application entrypoint
│   ├── package.json
│   └── vite.config.ts
│
├── docs/                           # Architecture diagrams & workflow schemas
└── README.md                       # Comprehensive project documentation
```

---

## ⚙️ Environment Variables Reference

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/command_center` | Async PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL for state and caching |
| `SECRET_KEY` | `command_center_secret_key_change_in_prod` | Secret key for JWT encoding/decoding |
| `ALGORITHM` | `HS256` | JWT cryptographic algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | JWT access token expiration in minutes |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Allowed CORS origins for frontend |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `GROQ_API_KEY` | `""` | Groq LLM API key |
| `GROQ_MODEL` | `groq/compound-mini` | Groq model identifier |
| `SARVAM_API_KEY` | `""` | Sarvam AI API key for Indian STT/TTS |
| `REFUND_THRESHOLD_AMOUNT` | `5000.0` | Maximum amount (INR) for automated refund approval |
| `RAG_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence transformer embedding model |
| `RAG_TOP_K` | `5` | Number of relevant chunks retrieved per query |
| `RAG_CACHE_TTL` | `300` | Redis RAG query cache TTL in seconds |

---

## 🔧 Troubleshooting

### 1. PostgreSQL Connection Refused
- **Symptom**: `asyncpg.exceptions.ConnectionDoesNotExistError` or `connection refused`.
- **Solution**: Ensure PostgreSQL service is running (`systemctl status postgresql` or Docker container is active) and database `command_center` has been created.

### 2. Redis Connection Warning
- **Symptom**: `Failed to connect to Redis at redis://localhost:6379/0`.
- **Solution**: Start Redis on port 6379 (`redis-server`). If Redis is disabled, the RAG engine and agent will automatically degrade to memory cache without crashing.

### 3. Microphone Permissions in Browser
- **Symptom**: Voice consultation shows audio muted or microphone blocked.
- **Solution**: Ensure your browser allows microphone permissions for `http://localhost:5173`. Alternatively, use the Text Chat input in the consultation interface.

### 4. ChromaDB & Sentence Transformer First Load
- **Symptom**: First RAG query takes 2-3 seconds.
- **Solution**: SentenceTransformer downloads `all-MiniLM-L6-v2` on the first run. The backend pre-warms the model during startup lifecycle so runtime queries execute in < 25ms.

---

## 📄 License
This project is proprietary and maintained for the InsureAI Command Center ecosystem.