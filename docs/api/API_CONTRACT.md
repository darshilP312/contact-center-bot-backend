# API Contract — Enterprise Voice-First AI Command Center
## Version: v1 | Last Updated: 2026-08-10

---

## Overview

The backend exposes two communication channels:
1. **WebSocket** at `ws://host:8000/api/v1/ws/{session_id}` — real-time bidirectional channel for audio + events
2. **REST HTTP** at `http://host:8000/api/v1/` — session lifecycle management

The complete OpenAPI 3.1 schema is auto-generated at `http://host:8000/api/v1/docs`.

---

## WebSocket Protocol

### Endpoint
```
ws://host:8000/api/v1/ws/{session_id}
```

### Frame Types

| Direction | Frame Type | Description |
|---|---|---|
| Client → Server | **Text (JSON)** | Control messages (see below) |
| Client → Server | **Binary** | Raw PCM 16kHz 16-bit mono audio bytes |
| Server → Client | **Text (JSON)** | Events and responses (see below) |
| Server → Client | **Binary** | TTS audio chunks (PCM or WAV bytes) |

---

### Client → Server: JSON Control Messages

#### `session.start`
Sent once when connection is established. Initialises session state.
```json
{
  "type": "session.start",
  "payload": {
    "language": "en",
    "domain": "insurance"
  }
}
```

#### `text.message`
Send a text message (chat mode — no audio).
```json
{
  "type": "text.message",
  "payload": {
    "text": "I want to file a claim for my car accident"
  }
}
```

#### `session.end`
Gracefully terminate the session.
```json
{
  "type": "session.end",
  "payload": {}
}
```

---

### Client → Server: Binary Audio Frames
```
Raw PCM bytes:
  - Sample rate: 16,000 Hz
  - Bit depth: 16-bit signed integer
  - Channels: 1 (mono)
  - Encoding: Little-endian
  - Frame size: 30ms recommended (480 samples = 960 bytes)
```

---

### Server → Client: JSON Event Messages

#### `transcript.partial`
Streaming partial STT result during active speech.
```json
{
  "type": "transcript.partial",
  "payload": {
    "text": "I want to file a clai...",
    "session_id": "sess_abc123"
  }
}
```

#### `transcript.final`
Final STT result after VAD silence detection.
```json
{
  "type": "transcript.final",
  "payload": {
    "text": "I want to file a claim for my car accident.",
    "session_id": "sess_abc123",
    "turn_count": 1
  }
}
```

#### `agent.thinking`
Emitted as each LangGraph node begins execution.
```json
{
  "type": "agent.thinking",
  "payload": {
    "node": "planner",
    "status": "running",
    "session_id": "sess_abc123"
  }
}
```
Possible `node` values: `conversation_understanding`, `planner`, `guardrails`, `business_router`, `rag`, `tool_caller`, `workflow_executor`, `response_generator`, `escalation_handler`

#### `intent.detected`
Emitted by `conversation_understanding` node.
```json
{
  "type": "intent.detected",
  "payload": {
    "name": "file_claim",
    "confidence": 0.94,
    "entities": {
      "incident_type": "car_accident",
      "incident_date": "2024-01-15"
    },
    "sentiment": "neutral",
    "session_id": "sess_abc123"
  }
}
```

#### `workflow.update`
Emitted by `business_router` and `workflow_executor` nodes.
```json
{
  "type": "workflow.update",
  "payload": {
    "workflow_name": "claim_filing",
    "current_step": "verify_documents",
    "completed_steps": ["authenticate", "verify_policy"],
    "total_steps": 6,
    "session_id": "sess_abc123"
  }
}
```

#### `response.text`
Agent's text response (may be chunked for streaming).
```json
{
  "type": "response.text",
  "payload": {
    "text": "I'm pulling up your policy now. I can see you're covered for collision damage.",
    "is_final": true,
    "rag_used": false,
    "session_id": "sess_abc123"
  }
}
```

#### `session.state`
Full session state snapshot (emitted after each turn completes).
```json
{
  "type": "session.state",
  "payload": {
    "session_id": "sess_abc123",
    "conversation": { /* ConversationState */ },
    "customer": { /* CustomerInfo */ },
    "intent": { /* IntentInfo */ },
    "workflow": { /* WorkflowState */ },
    "flags": { /* SessionFlags */ },
    "metrics": { /* ObservabilityMetrics */ }
  }
}
```

#### `session.escalated`
Emitted when the session is handed off to a human agent.
```json
{
  "type": "session.escalated",
  "payload": {
    "session_id": "sess_abc123",
    "escalation_reason": "Customer frustrated after 6 turns with unresolved claim",
    "transcript_summary": "Customer called about car accident claim filed on Jan 15...",
    "customer_info": { /* CustomerInfo — PII masked */ },
    "intent": { /* IntentInfo */ },
    "workflow": { /* WorkflowState */ },
    "flags": { /* SessionFlags */ },
    "final_sentiment": "frustrated",
    "timestamp": "2024-01-20T14:32:00Z"
  }
}
```

#### `metrics.update`
Observability metrics update (emitted after each turn).
```json
{
  "type": "metrics.update",
  "payload": {
    "session_id": "sess_abc123",
    "turn_latencies_ms": { "1": 1240, "2": 890 },
    "total_tokens_used": 3420,
    "total_cost": 0.0034,
    "tool_calls_made": 3,
    "glass_to_glass_ms": 1850
  }
}
```

#### `error`
Error event for client-facing failures.
```json
{
  "type": "error",
  "payload": {
    "code": "STT_TIMEOUT",
    "message": "Speech recognition timed out. Please try again.",
    "session_id": "sess_abc123",
    "recoverable": true
  }
}
```
Error codes: `STT_TIMEOUT`, `LLM_ERROR`, `TOOL_FAILURE`, `SESSION_NOT_FOUND`, `DOMAIN_NOT_LOADED`, `POLICY_VIOLATION`, `WEBSOCKET_ERROR`

---

### Server → Client: Binary TTS Audio Frames
```
TTS audio bytes:
  - Format: WAV (with header) or raw PCM — determined by TTS_OUTPUT_FORMAT env var
  - Sample rate: 22,050 Hz (Kokoro) or 24,000 Hz (edge-tts)
  - Channels: 1 (mono)
  - Streamed sentence-by-sentence (each binary frame = one synthesized sentence)
```

---

## REST API

### Base URL
```
http://host:8000/api/v1
```

### Endpoints

#### `GET /health`
Liveness check. Returns 200 if server is running.
```json
{ "status": "ok", "timestamp": "2024-01-20T14:32:00Z" }
```

#### `GET /ready`
Readiness check. Returns 200 only if all services are ready.
```json
{
  "status": "ready",
  "checks": {
    "redis": "ok",
    "domains_loaded": ["insurance"],
    "stt_model": "loaded",
    "tts_model": "loaded"
  }
}
```

#### `POST /sessions`
Create a new session. Returns session ID.
```json
// Request
{ "domain": "insurance", "language": "en", "channel": "voice" }

// Response 201
{ "session_id": "sess_abc123", "created_at": "2024-01-20T14:32:00Z", "domain": "insurance" }
```

#### `GET /sessions/{session_id}`
Get full session state.
```json
// Response 200
{
  "session_id": "sess_abc123",
  "conversation": { /* ConversationState */ },
  "customer": { /* CustomerInfo */ },
  "intent": { /* IntentInfo */ },
  "workflow": { /* WorkflowState */ },
  "flags": { /* SessionFlags */ },
  "metrics": { /* ObservabilityMetrics */ }
}
```

#### `DELETE /sessions/{session_id}`
End and clean up session.
```json
// Response 200
{ "session_id": "sess_abc123", "ended_at": "2024-01-20T14:45:00Z" }
```

#### `GET /sessions/{session_id}/transcript`
Get full conversation transcript.
```json
// Response 200
{
  "session_id": "sess_abc123",
  "entries": [
    { "role": "customer", "text": "I want to file a claim", "ts": "2024-01-20T14:32:05Z" },
    { "role": "agent", "text": "I can help you with that...", "ts": "2024-01-20T14:32:07Z" }
  ]
}
```

#### `GET /sessions/{session_id}/metrics`
Get observability metrics for session.
```json
// Response 200
{
  "session_id": "sess_abc123",
  "turn_latencies_ms": { "1": 1240 },
  "total_tokens_used": 3420,
  "total_cost": 0.0034,
  "tool_calls_made": 3
}
```

#### `GET /domains`
List all loaded domain plugins.
```json
// Response 200
{
  "domains": [
    { "domain_id": "insurance", "domain_name": "Insurance", "version": "1.0.0", "intents_count": 6 }
  ]
}
```

---

## Error Responses

All REST errors follow this schema:
```json
{
  "error": {
    "code": "SESSION_NOT_FOUND",
    "message": "Session sess_xyz not found or has expired",
    "request_id": "req_abc"
  }
}
```

HTTP status codes:
- `400` — Bad Request (invalid payload)
- `404` — Not Found (session, domain)
- `409` — Conflict (session already exists)
- `422` — Unprocessable Entity (validation error)
- `500` — Internal Server Error
- `503` — Service Unavailable (Redis down, domain not loaded)
