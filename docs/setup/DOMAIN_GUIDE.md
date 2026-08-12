# DOMAIN_GUIDE.md — Adding a New Domain Plugin
## Enterprise Voice-First AI Command Center

> This guide explains how to add a new domain (e.g., Telecom, Banking, E-commerce) to the platform.
> **No changes to existing Python files are required.** Domain plugins are pure YAML + optional tool files.

---

## Overview

A domain plugin consists of:
```
/backend/app/domains/<domain_name>/
├── domain.yaml              ← REQUIRED: Intent taxonomy, tools, RAG config
├── workflows/               ← Optional: Per-workflow step definitions
│   └── <workflow_name>.yaml
├── policies/                ← Optional: Domain-specific policy rules
│   └── rules.yaml
└── knowledge/               ← Optional: RAG source documents (Markdown)
    ├── faq.md
    └── <any_name>.md
```

---

## Step 1: Create the Domain Directory

```powershell
New-Item -Type Directory -Path "backend\app\domains\telecom"
New-Item -Type Directory -Path "backend\app\domains\telecom\workflows"
New-Item -Type Directory -Path "backend\app\domains\telecom\policies"
New-Item -Type Directory -Path "backend\app\domains\telecom\knowledge"
```

---

## Step 2: Create `domain.yaml`

This is the only required file. Copy and adapt from `domains/insurance/domain.yaml`.

```yaml
domain_id: "telecom"          # snake_case, unique
domain_name: "Telecom"        # Human-readable
version: "1.0.0"

intents:
  - name: report_outage
    description: "Customer reports a service outage or connectivity issue"
    required_entities: [account_number]
    optional_entities: [location, service_type]
    maps_to_workflow: outage_resolution
    maps_to_tools: [lookup_customer, create_ticket, send_sms]

  - name: billing_inquiry
    description: "Customer asks about their bill or charges"
    required_entities: [account_number]
    optional_entities: [billing_period]
    maps_to_workflow: billing_support
    maps_to_tools: [lookup_customer, lookup_invoice]

  - name: plan_upgrade
    description: "Customer wants to upgrade or change their service plan"
    required_entities: [account_number]
    optional_entities: [desired_plan, current_plan]
    maps_to_workflow: plan_change
    maps_to_tools: [lookup_customer, lookup_plans, process_plan_change]

  - name: general_query
    description: "General question not matching a specific intent"
    required_entities: []
    optional_entities: []
    maps_to_workflow: null
    maps_to_tools: []
    requires_rag: true

enabled_tools:
  - lookup_customer
  - verify_customer
  - create_ticket
  - send_sms
  - send_email
  - route_to_human_agent
  # Add telecom-specific tools here (must be implemented in tools/telecom/)

rag:
  knowledge_dir: "domains/telecom/knowledge/"
  chunk_size: 512
  chunk_overlap: 64
  embedding_model: "local"    # Uses sentence-transformers (configured globally)
```

---

## Step 3: Create Workflow YAMLs (Optional)

For each `maps_to_workflow` in your `domain.yaml`, create a corresponding workflow file:

```yaml
# workflows/outage_resolution.yaml
workflow_id: outage_resolution
workflow_name: "Outage Resolution"
description: "Guide customer through reporting and resolving a service outage"

steps:
  - id: authenticate
    name: "Authenticate Customer"
    description: "Verify customer identity"
    required_tools: [lookup_customer, verify_customer]
    required_entities: [account_number]
    next_step: diagnose_issue
    on_failure: escalate

  - id: diagnose_issue
    name: "Diagnose Issue"
    description: "Run remote diagnostics on customer line"
    required_tools: [run_line_diagnostic]
    required_entities: []
    next_step: create_ticket
    on_failure: escalate

  - id: create_ticket
    name: "Create Support Ticket"
    description: "Log the outage with a ticket"
    required_tools: [create_ticket]
    required_entities: []
    next_step: notify_customer
    on_failure: escalate

  - id: notify_customer
    name: "Notify Customer"
    description: "Send SMS with ticket ID and estimated resolution time"
    required_tools: [send_sms]
    required_entities: []
    next_step: null   # End of workflow
    on_failure: skip  # Non-critical step
```

---

## Step 4: Create Policy Rules (Optional)

```yaml
# policies/rules.yaml
domain: telecom
version: "1.0.0"

rules:
  - rule_id: TELECOM_001
    name: "Outage Escalation After 3 Failed Diagnostics"
    description: "Escalate to human agent if diagnostics fail 3 times"
    condition:
      field: working_memory.diagnostics_run
      operator: length_gte
      value: 3
    action: escalate
    escalation_reason: "Multiple diagnostic failures — requires level-2 support"

  - rule_id: TELECOM_002
    name: "Block Plan Upgrade Without Verification"
    description: "Customer must be verified before plan upgrades"
    condition:
      field: customer.verified
      operator: equals
      value: false
      context: intent_is_plan_upgrade
    action: block
    block_message: "Please verify your identity before making plan changes."
```

---

## Step 5: Add Knowledge Documents (Optional — for RAG)

Add Markdown files to `knowledge/`. These are automatically indexed at startup.

```markdown
<!-- knowledge/faq.md -->
# Telecom FAQ

## How do I report a service outage?
Call our 24/7 hotline or chat with our AI agent. Provide your account number and location.

## What is the typical resolution time for an outage?
Most outages are resolved within 4 hours. Critical issues affecting many customers are prioritized.
```

---

## Step 6: Add Domain-Specific Tools (Optional)

If your domain needs tools beyond the core set (`lookup_customer`, `create_ticket`, etc.):

```python
# backend/app/tools/telecom/diagnostics.py
from app.tools.base import BaseTool
from pydantic import BaseModel
import hashlib

class DiagnosticInput(BaseModel):
    account_number: str
    service_type: str = "broadband"

class DiagnosticResult(BaseModel):
    account_number: str
    status: str
    signal_strength: str
    packet_loss_pct: float
    recommendation: str

class RunLineDiagnosticTool(BaseTool):
    name = "run_line_diagnostic"
    description = "Run remote diagnostics on a customer's service line"
    domains = ["telecom"]
    input_schema = DiagnosticInput
    output_schema = DiagnosticResult

    async def execute(self, input_data: DiagnosticInput) -> DiagnosticResult:
        # TODO: Replace with real NOC API call
        seed = hashlib.md5(input_data.account_number.encode()).hexdigest()[:8]
        return DiagnosticResult(
            account_number=input_data.account_number,
            status="degraded",
            signal_strength=f"{int(seed[:2], 16) % 30 + 60}%",
            packet_loss_pct=round(int(seed[2:4], 16) / 256 * 5, 2),
            recommendation="Reset modem and run diagnostics again in 10 minutes"
        )
```

Add the tool name to `enabled_tools` in your `domain.yaml`.

---

## Step 7: Restart the Backend

```powershell
.\scripts\start_backend.ps1
```

The domain plugin loader in `lifespan.py` will automatically:
1. Discover your new `domain.yaml`
2. Register all enabled tools for the domain
3. Load and index knowledge documents into FAISS
4. Make the domain available for sessions

Verify it loaded:
```powershell
Invoke-RestMethod http://localhost:8000/api/v1/domains
```

Expected output includes `"domain_id": "telecom"`.

---

## Checklist for New Domain

- [ ] `domain.yaml` created with valid intent taxonomy
- [ ] All `maps_to_workflow` values have corresponding YAML files in `workflows/`
- [ ] All `maps_to_tools` values exist in the tool registry (core or domain-specific)
- [ ] Knowledge documents added to `knowledge/` (at least `faq.md`)
- [ ] Domain-specific tools implemented in `tools/<domain_name>/` (if needed)
- [ ] Backend restarted and `GET /api/v1/domains` confirms domain is loaded
- [ ] Tested with a sample conversation in the UI (select domain from dropdown)
- [ ] `TRACKER.md` updated with the new domain entry
