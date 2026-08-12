import React, { useEffect, useCallback } from "react";
import { ConnectionStatusBar } from "../components/layout/ConnectionStatusBar";
import { VoicePanel } from "../components/voice/VoicePanel";
import { ChatPanel } from "../components/chat/ChatPanel";
import { TranscriptPanel } from "../components/chat/TranscriptPanel";
import { AIThinkingPanel } from "../components/analytics/AIThinkingPanel";
import { WorkflowProgressPanel } from "../components/workflow/WorkflowProgressPanel";
import { ActiveCasePanel } from "../components/analytics/ActiveCasePanel";
import { useWebSocket } from "../hooks/useWebSocket";
import { useVoiceStream } from "../hooks/useVoiceStream";
import { useSessionState } from "../hooks/useSessionState";
import { useSessionStore } from "../store/sessionStore";
import { useTranscriptStore } from "../store/transcriptStore";
import { useMetricsStore } from "../store/metricsStore";

export function CommandCenter() {
  const { sessionId, domain, domains, setDomain, startNewSession, endSession } = useSessionState();
  const { connectionStatus, lastError } = useSessionStore();
  const { partialTranscript } = useTranscriptStore();

  const { connect, disconnect, sendText, sendAudio } = useWebSocket(sessionId);

  const { isRecording, startRecording, stopRecording } = useVoiceStream({
    onAudioChunk: sendAudio,
    onError: (err) => console.error("Mic error:", err),
  });

  const isConnected = connectionStatus === "connected";

  const handleConnect = useCallback(async () => {
    const sid = await startNewSession();
    await connect();
  }, [startNewSession, connect]);

  const handleDisconnect = useCallback(async () => {
    if (isRecording) stopRecording();
    disconnect();
    await endSession();
  }, [isRecording, stopRecording, disconnect, endSession]);

  const handleToggleRecording = useCallback(() => {
    if (isRecording) stopRecording();
    else startRecording();
  }, [isRecording, startRecording, stopRecording]);

  // Auto-connect on sessionId set
  useEffect(() => {
    if (sessionId && connectionStatus === "idle") {
      connect();
    }
  }, [sessionId]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", position: "relative", zIndex: 1 }}>
      {/* Top bar */}
      <ConnectionStatusBar />

      {/* Domain selector + session controls */}
      <div
        style={{
          padding: "10px 20px",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          gap: 12,
          flexShrink: 0,
          background: "rgba(5,11,26,0.6)",
          backdropFilter: "blur(8px)",
        }}
      >
        <span style={{ fontSize: 12, color: "var(--text-muted)", whiteSpace: "nowrap" }}>Domain:</span>
        <select
          id="domain-selector"
          className="input select"
          style={{ width: 180, padding: "6px 36px 6px 10px" }}
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          disabled={isConnected}
        >
          {domains.length === 0 ? (
            <option value="insurance">Insurance (default)</option>
          ) : (
            domains.map((d) => (
              <option key={d.domain_id} value={d.domain_id}>
                {d.domain_name}
              </option>
            ))
          )}
        </select>

        {lastError && (
          <div
            style={{
              fontSize: 12,
              color: "var(--accent-red)",
              padding: "4px 12px",
              background: "rgba(239,68,68,0.1)",
              border: "1px solid rgba(239,68,68,0.2)",
              borderRadius: "var(--radius-sm)",
            }}
          >
            ⚠ {lastError}
          </div>
        )}

        <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
          {sessionId && (
            <span className="font-mono" style={{ fontSize: 11, color: "var(--text-muted)" }}>
              {sessionId}
            </span>
          )}
        </div>
      </div>

      {/* 6-panel grid layout */}
      <div
        style={{
          flex: 1,
          display: "grid",
          gridTemplateColumns: "280px 1fr 1fr 280px",
          gridTemplateRows: "1fr 1fr",
          gap: 12,
          padding: 12,
          overflow: "hidden",
          minHeight: 0,
        }}
      >
        {/* Col 1, Row 1: Voice Panel */}
        <div style={{ gridColumn: 1, gridRow: 1, minHeight: 0, overflow: "hidden" }}>
          <VoicePanel
            isRecording={isRecording}
            onToggleRecording={handleToggleRecording}
            onConnect={handleConnect}
            onDisconnect={handleDisconnect}
            partialTranscript={partialTranscript}
          />
        </div>

        {/* Col 2-3, Row 1: Chat Panel (spans 2 columns) */}
        <div style={{ gridColumn: "2 / 4", gridRow: 1, minHeight: 0, overflow: "hidden" }}>
          <ChatPanel onSendMessage={sendText} isConnected={isConnected} />
        </div>

        {/* Col 4, Row 1: AI Thinking Panel */}
        <div style={{ gridColumn: 4, gridRow: 1, minHeight: 0, overflow: "hidden" }}>
          <AIThinkingPanel />
        </div>

        {/* Col 1, Row 2: Active Case Panel */}
        <div style={{ gridColumn: 1, gridRow: 2, minHeight: 0, overflow: "hidden" }}>
          <ActiveCasePanel />
        </div>

        {/* Col 2, Row 2: Transcript Panel */}
        <div style={{ gridColumn: 2, gridRow: 2, minHeight: 0, overflow: "hidden" }}>
          <TranscriptPanel />
        </div>

        {/* Col 3, Row 2: Workflow Progress Panel */}
        <div style={{ gridColumn: 3, gridRow: 2, minHeight: 0, overflow: "hidden" }}>
          <WorkflowProgressPanel />
        </div>

        {/* Col 4, Row 2: Session Metrics */}
        <div style={{ gridColumn: 4, gridRow: 2, minHeight: 0, overflow: "hidden" }}>
          <SessionMetricsPanel />
        </div>
      </div>
    </div>
  );
}

// ── Inline mini-component: Session Metrics ────────────────────────────────────
function SessionMetricsPanel() {
  const { metrics, flags } = useSessionStore();
  const metricsStore = useMetricsStore();

  const totalTokens = (metrics?.total_tokens_used && metrics.total_tokens_used > 0) ? metrics.total_tokens_used : metricsStore.totalTokens;
  const totalCost = (metrics?.total_cost && metrics.total_cost > 0) ? metrics.total_cost : metricsStore.totalCost;
  const toolCalls = (metrics?.tool_calls_made && metrics.tool_calls_made > 0) ? metrics.tool_calls_made : metricsStore.toolCallsMade;
  const turnCount = (metrics?.turn_latencies_ms && Object.keys(metrics.turn_latencies_ms).length > 0) ? Object.keys(metrics.turn_latencies_ms).length : metricsStore.turnLatencies.length;

  return (
    <div className="glass-card flex flex-col" style={{ height: "100%" }}>
      <div className="section-header">
        <span>📊</span>
        <span>Session Metrics</span>
      </div>
      <div style={{ padding: "12px 16px", flex: 1, display: "flex", flexDirection: "column", gap: 10 }}>
        <MetricRow label="Turn Count" value={turnCount} unit="" />
        <MetricRow label="Tokens Used" value={totalTokens} unit="tk" />
        <MetricRow label="Est. Cost" value={`$${totalCost.toFixed(4)}`} unit="" />
        <MetricRow label="Tool Calls" value={toolCalls} unit="" />

        {flags && (
          <div style={{ marginTop: 8, borderTop: "1px solid var(--border)", paddingTop: 12 }}>
            <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>Flags</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {[
                ["rag_used", "RAG Used", "badge-cyan"],
                ["ticket_created", "Ticket Created", "badge-green"],
                ["engineer_booked", "Surveyor Booked", "badge-blue"],
                ["escalated", "Escalated", "badge-red"],
                ["awaiting_approval", "Approval Pending", "badge-amber"],
              ].map(([flag, label, color]) => (
                <div key={flag} style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{label}</span>
                  <div className={`badge ${(flags as Record<string, unknown>)[flag] ? color : ""}`}
                    style={{ opacity: (flags as Record<string, unknown>)[flag] ? 1 : 0.25, fontSize: 10, padding: "2px 8px" }}>
                    {(flags as Record<string, unknown>)[flag] ? "Yes" : "No"}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function MetricRow({ label, value, unit }: { label: string; value: string | number; unit: string }) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", padding: "4px 0" }}>
      <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{label}</span>
      <span className="font-mono" style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)" }}>
        {value}<span style={{ fontSize: 10, color: "var(--text-muted)" }}>{unit && ` ${unit}`}</span>
      </span>
    </div>
  );
}
