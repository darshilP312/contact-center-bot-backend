/**
 * wsTypes.ts — WebSocket event contract types (frozen after Week 1).
 * Shared by AudioClient, store, and all components.
 */

// ── CLIENT → SERVER ──────────────────────────────────────────────────────────

export interface ClientControlStart {
  type: 'control';
  action: 'start';
  session_id?: string;
}
export interface ClientControlStop { type: 'control'; action: 'stop'; }
export interface ClientControlBargeIn { type: 'control'; action: 'barge_in'; }
export interface ClientAudioChunk {
  type: 'audio_chunk';
  seq: number;
  data: string; // Base64 PCM16 16kHz mono
  sample_rate?: number;
}
export interface ClientTextInput { type: 'text_input'; text: string; }

export type ClientMessage =
  | ClientControlStart | ClientControlStop | ClientControlBargeIn
  | ClientAudioChunk | ClientTextInput;

// ── SERVER → CLIENT ──────────────────────────────────────────────────────────

export interface RagCitation {
  source: string;
  chunk: string;
  score: number;
}

export interface ServerTranscriptPartial {
  type: 'transcript_partial';
  text: string;
  confidence?: number;
}
export interface ServerTranscriptFinal {
  type: 'transcript_final';
  text: string;
  confidence: number;
}
export interface ServerAssistantText {
  type: 'assistant_text';
  text: string;
  is_streaming: boolean;
  rag_citations?: RagCitation[];
}
export interface ServerAudioChunk {
  type: 'audio_chunk';
  seq: number;
  data: string;
  sample_rate: number;
}
export interface ServerStateUpdate {
  type: 'state_update';
  workflow_name: string | null;
  workflow_step: string | null;
  completed_steps: string[];
  flags: {
    ticket_created: boolean;
    engineer_booked: boolean;
    escalated: boolean;
    awaiting_approval: boolean;
    refund_triggered: boolean;
    rag_used: boolean;
    barge_in_detected: boolean;
  };
  sentiment: 'neutral' | 'frustrated' | 'angry' | 'satisfied';
  customer_tier: string | null;
}
export interface ServerTicket {
  type: 'ticket';
  id: string;
  ticket_type: string;
  summary: string;
}
export interface ServerPolicyBlock {
  type: 'policy_block';
  rule: string;
  message: string;
  required_action: string;
}
export interface ServerHandoffSummary {
  type: 'handoff_summary';
  summary: string;
  ticket_id: string | null;
  sentiment: string;
}
export interface ServerObservability {
  type: 'observability';
  turn: number;
  stage_latencies_ms: Record<string, number>;
  total_tokens: number;
  cost_usd: number;
  tool_calls: string[];
  intent: string | null;
}
export interface ServerError {
  type: 'error';
  code: string;
  message: string;
}

export type ServerMessage =
  | ServerTranscriptPartial | ServerTranscriptFinal | ServerAssistantText
  | ServerAudioChunk | ServerStateUpdate | ServerTicket | ServerPolicyBlock
  | ServerHandoffSummary | ServerObservability | ServerError;
