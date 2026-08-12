# RULES.md — Immutable Project Law
## Enterprise Voice-First AI Command Center

> **This document is set in stone after initial agreement. Changes require explicit team consensus and a new ADL entry in BRAIN.md.**

---

## 1. Coding Standards & Naming Conventions

### Python (Backend)
- **Style**: PEP 8, enforced via `ruff` (linter) and `black` (formatter).
- **Naming**:
  - Variables, functions, methods: `snake_case`
  - Classes: `PascalCase`
  - Constants and env var names: `SCREAMING_SNAKE_CASE`
  - Private methods/attributes: `_leading_underscore`
  - Module files: `snake_case.py`
- **Type hints**: Required on all public function signatures. Use `from __future__ import annotations` for forward refs.
- **Docstrings**: Google-style docstrings on all public classes and functions.
- **Async**: All I/O-bound operations must be `async def`. No `time.sleep()`, no blocking `requests` calls inside async context.
- **Pydantic**: Use Pydantic v2 for all data models. No `dict` returns where a model exists.

### TypeScript (Frontend)
- **Style**: ESLint + Prettier enforced.
- **Naming**:
  - Variables, functions: `camelCase`
  - React components, types, interfaces: `PascalCase`
  - Constants: `SCREAMING_SNAKE_CASE`
  - Files: `PascalCase.tsx` for components, `camelCase.ts` for utilities/hooks
- **Strict mode**: `"strict": true` in `tsconfig.json`. No `any` type without `// @ts-expect-error` + justification comment.
- **API calls**: ALL backend communication must go through `src/api/` only. Zero direct `fetch()`, `axios()`, or `new WebSocket()` in components or hooks.

---

## 2. API Contract Rules

- **No breaking changes** to `/api/v1/` endpoints without bumping to `/api/v2/`.
- Breaking change = removing a field, changing a field type, changing an endpoint path.
- Non-breaking = adding optional fields, adding new endpoints.
- **WebSocket message protocol** is versioned in `docs/api/API_CONTRACT.md`. Any new message type must be documented there before implementation.
- **OpenAPI schema** must remain valid. CI must run `fastapi openapi-check` (or equivalent) on every backend change.

---

## 3. Git Commit Message Format

**Conventional Commits** — strictly enforced.

```
<type>(<scope>): <short description>

[optional body]

[optional footer]
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`, `ci`

**Scopes**: `backend`, `frontend`, `orchestrator`, `tools`, `stt`, `tts`, `domains`, `infra`, `docs`

**Examples**:
```
feat(orchestrator): add reasoning loop cap at 3 iterations
fix(stt): handle empty audio buffer in VAD pipeline
docs(domains): add DOMAIN_GUIDE.md for new domain onboarding
chore(deps): pin faster-whisper to 1.0.3
```

---

## 4. Test Coverage Requirements

| Component | Minimum Coverage |
|---|---|
| `backend/app/services/` | 70% |
| `backend/app/tools/` | 70% |
| `backend/app/orchestrator/nodes/` | 50% |
| `backend/app/orchestrator/graph.py` | 50% |
| `backend/app/policies/` | 70% |
| `backend/app/api/` | 60% |
| Frontend components | 30% (E2E via Playwright preferred) |

- Run: `pytest --cov=app --cov-fail-under=60 backend/tests/`
- All new features must ship with tests. PRs without tests for new code are rejected.

---

## 5. Environment Variable Rules

- **Naming**: `SCREAMING_SNAKE_CASE` for all env vars.
- **No hardcoded defaults for secrets**: `LLM_API_KEY`, `REDIS_URL`, `LANGFUSE_SECRET_KEY`, etc. must raise a `ValueError` at startup if not set (except truly optional ones like Langfuse).
- **Hardcoded defaults allowed** only for non-sensitive config: `STT_MODEL_SIZE=base`, `TTS_PROVIDER=kokoro`, `LOG_LEVEL=INFO`.
- **`.env.example`** is the only committed env file. Actual `.env` is in `.gitignore`.
- **Validation**: All env vars are validated at startup via Pydantic `Settings` class in `backend/app/core/config.py`. The app must fail fast with a clear error if required vars are missing.

---

## 6. Secret Management

- **No secrets ever in source code**. No API keys, passwords, connection strings hardcoded anywhere.
- **No secrets in committed `.env` files**. Only `.env.example` is committed.
- `.env` is in `.gitignore` and must never be committed.
- Production secrets must be stored in Azure Key Vault and injected as environment variables at deploy time.
- In code reviews: reject any PR that introduces a secret, even in comments or test fixtures.

---

## 7. Logging Standards

- **Format**: Structured JSON only. No `print()`, no unstructured `logging.info("msg")`.
- **Library**: `structlog` configured to output JSON in production, colored console in development.
- **Required fields** on every log event:
  - `session_id` (string or `"none"` if pre-session)
  - `trace_id` (string or `"none"`)
  - `node` (the LangGraph node or service name, e.g. `"planner"`, `"stt_pipeline"`)
  - `level` (DEBUG/INFO/WARNING/ERROR/CRITICAL)
  - `timestamp` (ISO 8601 UTC)
- **PII rule**: Phone numbers, account numbers, and government IDs must NEVER appear in log output. The `guardrails` node masks these before they enter any prompt or log.
- **Log levels**:
  - DEBUG: Detailed execution tracing (disabled in production)
  - INFO: Normal operational events (session start, intent detected, tool called)
  - WARNING: Non-critical anomalies (retry triggered, fallback TTS used)
  - ERROR: Failures that impact a session (tool error, LLM timeout)
  - CRITICAL: System-level failures (Redis unavailable, domain plugin failed to load)

---

## 8. Domain Plugin Rules

- **New domains via YAML config only**. Adding a new domain must require:
  1. A new directory under `/backend/app/domains/<domain_name>/`
  2. A `domain.yaml` satisfying the schema in `_base/domain_schema.yaml`
  3. Optional: workflow YAMLs, policy rules YAML, knowledge documents
  4. Optional: domain-specific Python tool implementations
  5. **No changes to any existing Python files in the orchestrator, router, or policy engine**
- **Tool registration**: Domain tools self-register by declaring `domains: ["insurance"]` in their `BaseTool` subclass. The `ToolRegistry` discovers them at startup.
- **Intent taxonomy**: All intents for a domain are defined in `domain.yaml`. The `conversation_understanding` node loads the active domain's taxonomy at runtime.
- **Workflow definitions**: Workflow YAML files are the single source of truth for step sequences. The `workflow_executor` node reads them — it contains no hardcoded workflow logic.

---

## 9. Infrastructure Rules

- **No Docker. Ever.** This is a hard constraint from the Azure Virtual Desktop environment.
- **PowerShell only** for scripts. No bash, no shell, no bat files.
- **Idempotent setup scripts**: `setup_env.ps1` must be safely re-runnable. Use `winget` with `--accept-source-agreements` and handle already-installed cases gracefully.
- **Service management**: Backend and frontend are started via `scripts/start_backend.ps1` and `scripts/start_frontend.ps1`. No service installers for development.
- **Port conventions**: Backend on `8000`, Frontend dev server on `5173`. Both configurable via env.

---

## 10. Code Review Checklist

Before merging any PR, verify:
- [ ] No hardcoded secrets or API keys
- [ ] All new public functions have type hints and docstrings
- [ ] No `print()` statements (use `structlog`)
- [ ] No `any` types in TypeScript without justification comment
- [ ] No direct `fetch()`/`WebSocket()` in frontend components (must go through `src/api/`)
- [ ] Tests written for new code
- [ ] `TRACKER.md` updated with the change
- [ ] `BRAIN.md` updated if an architecture decision was made
- [ ] Commit message follows Conventional Commits format
