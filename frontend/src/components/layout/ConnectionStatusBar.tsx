import React from "react";
import { Wifi, WifiOff, Loader2, AlertCircle, Activity } from "lucide-react";
import { useSessionStore } from "../../store/sessionStore";

export function ConnectionStatusBar() {
  const { connectionStatus, domain, language, sessionId, escalated, thinkingNodes } =
    useSessionStore();

  const statusConfig = {
    idle: { label: "Idle", color: "idle", Icon: WifiOff },
    connecting: { label: "Connecting...", color: "connecting", Icon: Loader2 },
    connected: { label: "Live", color: "connected", Icon: Wifi },
    reconnecting: { label: "Reconnecting...", color: "connecting", Icon: Loader2 },
    disconnected: { label: "Disconnected", color: "idle", Icon: WifiOff },
    error: { label: "Connection Error", color: "error", Icon: AlertCircle },
  } as const;

  const cfg = statusConfig[connectionStatus] ?? statusConfig.idle;

  return (
    <header
      style={{
        height: 52,
        background: "rgba(5,11,26,0.95)",
        borderBottom: "1px solid var(--border)",
        backdropFilter: "blur(12px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 20px",
        flexShrink: 0,
        zIndex: 100,
        position: "relative",
      }}
    >
      {/* Left — brand */}
      <div className="flex items-center gap-3">
        <div
          style={{
            width: 30,
            height: 30,
            borderRadius: 8,
            background: "linear-gradient(135deg, var(--accent-blue), var(--accent-violet))",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 0 16px rgba(59,130,246,0.4)",
          }}
        >
          <Activity size={16} color="white" />
        </div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.02em" }}>
            AI Command Center
          </div>
          <div style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
            Enterprise Voice AI
          </div>
        </div>
      </div>

      {/* Center — thinking nodes */}
      {thinkingNodes.length > 0 && (
        <div className="flex items-center gap-2">
          {thinkingNodes.map((node) => (
            <div key={node} className="badge badge-blue" style={{ animation: "blink 1s ease-in-out infinite" }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--accent-blue)", display: "inline-block" }} />
              {node.replace(/_/g, " ")}
            </div>
          ))}
        </div>
      )}
      {escalated && (
        <div className="badge badge-amber">
          <AlertCircle size={11} />
          Escalated to Human Agent
        </div>
      )}

      {/* Right — status */}
      <div className="flex items-center gap-3">
        {sessionId && (
          <span className="font-mono text-xs" style={{ color: "var(--text-muted)" }}>
            {sessionId.slice(0, 16)}…
          </span>
        )}
        <span className="badge badge-cyan">{domain}</span>
        <span className="badge badge-violet">{language.toUpperCase()}</span>
        <div className="flex items-center gap-2">
          <div className={`status-dot ${cfg.color}`} />
          <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>{cfg.label}</span>
        </div>
      </div>
    </header>
  );
}
