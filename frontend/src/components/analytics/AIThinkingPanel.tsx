import React from "react";
import { Brain, ShieldCheck, ShieldX, ShieldAlert } from "lucide-react";
import { useSessionStore } from "../../store/sessionStore";
import { useMetricsStore } from "../../store/metricsStore";
import type { PolicyEvaluation } from "../../api/types";

// Singleton state for planner decisions (updated via WS, not in Zustand)
let _plannerDecision: {
  intent_type?: string;
  tools_to_call?: string[];
  policy_evaluations?: PolicyEvaluation[];
} = {};
export function updatePlannerDecision(d: typeof _plannerDecision) {
  _plannerDecision = { ..._plannerDecision, ...d };
}

const NODE_LABELS: Record<string, string> = {
  conversation_understanding: "Understanding Intent",
  guardrails: "Policy Check",
  business_router: "Routing",
  planner: "Planning Actions",
  rag: "Knowledge Retrieval",
  tool_caller: "Calling Tools",
  workflow_executor: "Executing Workflow",
  response_generator: "Generating Response",
  escalation_handler: "Escalating",
};

const NODE_COLORS: Record<string, string> = {
  conversation_understanding: "var(--accent-blue)",
  guardrails: "var(--accent-amber)",
  business_router: "var(--accent-cyan)",
  planner: "var(--accent-violet)",
  rag: "var(--accent-green)",
  tool_caller: "var(--accent-cyan)",
  workflow_executor: "var(--accent-blue)",
  response_generator: "var(--accent-green)",
  escalation_handler: "var(--accent-red)",
};

const GRAPH_NODES = [
  "conversation_understanding",
  "guardrails",
  "business_router",
  "planner",
  "rag",
  "tool_caller",
  "workflow_executor",
  "response_generator",
];

export function AIThinkingPanel() {
  const { thinkingNodes, intent } = useSessionStore();
  const { avgLatencyMs, lastTurnMs, totalTokens, toolCallsMade } = useMetricsStore();

  return (
    <div className="glass-card flex flex-col" style={{ height: "100%" }}>
      <div className="section-header">
        <Brain size={14} className="icon" />
        <span>AI Orchestrator</span>
        {thinkingNodes.length > 0 && (
          <div className="thinking-bar" style={{ flex: 1, marginLeft: 8 }} />
        )}
      </div>

      <div style={{ padding: "12px 16px", flex: 1, minHeight: 0, overflowY: "auto", display: "flex", flexDirection: "column", gap: 12 }}>

        {/* Intent type badge */}
        {intent?.intent_type && (
          <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 12px",
            borderRadius: "var(--radius-md)",
            background: intent.intent_type === "INFORMATIONAL_RAG"
              ? "rgba(6,182,212,0.08)" : intent.intent_type === "ACTIONAL_WORKFLOW"
              ? "rgba(59,130,246,0.08)" : "rgba(139,92,246,0.08)",
            border: `1px solid ${intent.intent_type === "INFORMATIONAL_RAG"
              ? "rgba(6,182,212,0.2)" : intent.intent_type === "ACTIONAL_WORKFLOW"
              ? "rgba(59,130,246,0.2)" : "rgba(139,92,246,0.2)"}`,
          }}>
            <span style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>Decision</span>
            <span className={`badge ${
              intent.intent_type === "INFORMATIONAL_RAG" ? "badge-cyan"
              : intent.intent_type === "ACTIONAL_WORKFLOW" ? "badge-blue"
              : "badge-violet"}`}>
              {intent.intent_type.replace(/_/g, " ")}
            </span>
          </div>
        )}

        {/* LangGraph pipeline */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
            Pipeline
          </div>
          {GRAPH_NODES.map((node) => {
            const isActive = thinkingNodes.includes(node);
            const color = NODE_COLORS[node] ?? "var(--accent-blue)";
            return (
              <div
                key={node}
                style={{
                  display: "flex", alignItems: "center", gap: 10, padding: "8px 12px",
                  borderRadius: "var(--radius-sm)",
                  background: isActive ? `${color}18` : "rgba(255,255,255,0.02)",
                  border: `1px solid ${isActive ? color + "40" : "var(--border)"}`,
                  transition: "all 0.3s",
                }}
              >
                <div
                  style={{
                    width: 8, height: 8, borderRadius: "50%", flexShrink: 0,
                    background: isActive ? color : "var(--text-muted)",
                    boxShadow: isActive ? `0 0 10px ${color}` : "none",
                    animation: isActive ? "pulse-glow 1s ease-in-out infinite" : "none",
                  }}
                />
                <span style={{ fontSize: 12, color: isActive ? "var(--text-primary)" : "var(--text-muted)", fontWeight: isActive ? 600 : 400 }}>
                  {NODE_LABELS[node] ?? node}
                </span>
                {isActive && (
                  <span style={{ marginLeft: "auto", fontSize: 10, color: color, fontWeight: 600 }}>ACTIVE</span>
                )}
              </div>
            );
          })}
        </div>

        {/* Intent info */}
        {intent?.name && (
          <div style={{ borderTop: "1px solid var(--border)", paddingTop: 12 }}>
            <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
              Detected Intent
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <span className="badge badge-blue">{intent.name.replace(/_/g, " ")}</span>
              <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                {(intent.confidence * 100).toFixed(0)}% confidence
              </span>
            </div>
            {/* Progress */}
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${intent.confidence * 100}%` }} />
            </div>

            {/* Entities */}
            {Object.keys(intent.entities ?? {}).length > 0 && (
              <div style={{ marginTop: 10, display: "flex", flexWrap: "wrap", gap: 6 }}>
                {Object.entries(intent.entities).map(([k, v]) => (
                  <div key={k} className="entity-chip">
                    <span style={{ color: "var(--text-muted)" }}>{k}:</span> {v}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Performance metrics */}
        <div style={{ borderTop: "1px solid var(--border)", paddingTop: 12, marginTop: "auto" }}>
          <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
            Performance
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <div className="metric-card">
              <div className="metric-value" style={{ fontSize: 18 }}>{avgLatencyMs}<span style={{ fontSize: 11, fontWeight: 400 }}>ms</span></div>
              <div className="metric-label">Avg Latency</div>
            </div>
            <div className="metric-card">
              <div className="metric-value" style={{ fontSize: 18 }}>{lastTurnMs}<span style={{ fontSize: 11, fontWeight: 400 }}>ms</span></div>
              <div className="metric-label">Last Turn</div>
            </div>
            <div className="metric-card">
              <div className="metric-value" style={{ fontSize: 18 }}>{totalTokens.toLocaleString()}</div>
              <div className="metric-label">Tokens Used</div>
            </div>
            <div className="metric-card">
              <div className="metric-value" style={{ fontSize: 18 }}>{toolCallsMade}</div>
              <div className="metric-label">Tool Calls</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
