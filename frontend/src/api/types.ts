// WebSocket event types matching the backend API contract

export type WebSocketMessageType =
  | "session.start"
  | "session.end"
  | "session.state"
  | "session.escalated"
  | "text.message"
  | "transcript.partial"
  | "transcript.final"
  | "agent.thinking"
  | "intent.detected"
  | "workflow.update"
  | "planner.decision"
  | "response.text"
  | "metrics.update"
  | "error";

export interface WSMessage<T = unknown> {
  type: WebSocketMessageType;
  payload: T;
}

export interface SessionState {
  session_id: string;
  domain: string;
  language: string;
  status: "active" | "escalated" | "ended";
  conversation: ConversationState;
  customer: CustomerInfo;
  intent: IntentState;
  workflow: WorkflowState;
  flags: SessionFlags;
  metrics: MetricsState;
}

export interface ConversationState {
  session_id: string;
  channel: "voice" | "chat" | "hybrid";
  sentiment: "frustrated" | "neutral" | "satisfied" | "urgent";
  turn_count: number;
  handoff_summary?: string;
}

export interface CustomerInfo {
  session_id: string;
  verified: boolean;
  customer_id?: string;
  name?: string;
  tier?: "standard" | "premium" | "enterprise";
  phone?: string;
  account_no?: string;
}

export interface IntentState {
  session_id: string;
  name?: string;
  /** INFORMATIONAL_RAG | ACTIONAL_WORKFLOW | DIAGNOSTIC_ACTION */
  intent_type?: string;
  confidence: number;
  entities: Record<string, string>;
  secondary_intents: string[];
}

export interface WorkflowState {
  session_id: string;
  name?: string;
  step?: string;
  completed_steps: string[];
  step_results: Record<string, unknown>;
}

export interface SessionFlags {
  session_id: string;
  ticket_created: boolean;
  engineer_booked: boolean;
  escalated: boolean;
  awaiting_approval: boolean;
  refund_triggered: boolean;
  rag_used: boolean;
  barge_in_detected: boolean;
}

export interface MetricsState {
  session_id: string;
  turn_latencies_ms: Record<string, number>;
  total_tokens_used: number;
  total_cost: number;
  tool_calls_made: number;
}

export interface TranscriptEntry {
  role: "customer" | "agent" | "system";
  text: string;
  ts: string;
  rag_citations?: string[];
}

export interface ThinkingEvent {
  node: string;
  status: "running" | "complete" | "error";
}

export interface PolicyEvaluation {
  rule_checked: string;
  passed: boolean;
  action_taken: "proceed" | "block" | "escalate" | "request_approval";
  escalation_reason?: string;
  approval_reason?: string;
  redirect_tool?: string;
}

export interface PlannerDecisionEvent {
  intent_type: "INFORMATIONAL_RAG" | "ACTIONAL_WORKFLOW" | "DIAGNOSTIC_ACTION";
  tools_to_call: string[];
  requires_rag: boolean;
  clarification_needed: boolean;
  policy_evaluations: PolicyEvaluation[];
  session_id: string;
}

export interface IntentDetectedEvent {
  name: string;
  confidence: number;
  entities: Record<string, string>;
  sentiment: string;
  session_id: string;
}

export interface WorkflowUpdateEvent {
  workflow_name: string;
  current_step?: string;
  completed_steps: string[];
  total_steps: number;
  session_id: string;
  step_complete?: boolean;
}

export interface ErrorEvent {
  code: string;
  message: string;
  session_id: string;
  recoverable: boolean;
}

export interface MetricsUpdateEvent extends MetricsState {
  glass_to_glass_ms?: number;
}

export interface Domain {
  domain_id: string;
  domain_name: string;
  version: string;
  intents_count: number;
  enabled_tools: string[];
  has_rag: boolean;
}
