import React from "react";
import { User, Shield, Ticket, Clock } from "lucide-react";
import { useSessionStore } from "../../store/sessionStore";

const tierColors: Record<string, string> = {
  standard: "badge-blue",
  premium: "badge-amber",
  enterprise: "badge-violet",
};

export function ActiveCasePanel() {
  const { customer, flags, conversation, intent } = useSessionStore();

  const activeFlags = flags
    ? Object.entries(flags)
        .filter(([k, v]) => v === true && k !== "session_id")
        .map(([k]) => k)
    : [];

  const flagLabels: Record<string, { label: string; color: string }> = {
    ticket_created: { label: "Ticket Created", color: "badge-green" },
    engineer_booked: { label: "Surveyor Booked", color: "badge-cyan" },
    escalated: { label: "Escalated", color: "badge-red" },
    awaiting_approval: { label: "Awaiting Approval", color: "badge-amber" },
    refund_triggered: { label: "Refund Initiated", color: "badge-violet" },
    rag_used: { label: "KB Consulted", color: "badge-blue" },
    barge_in_detected: { label: "Barge-In", color: "badge-amber" },
  };

  return (
    <div className="glass-card flex flex-col" style={{ height: "100%" }}>
      <div className="section-header">
        <User size={14} className="icon" />
        <span>Active Case</span>
      </div>

      <div style={{ padding: "12px 16px", flex: 1, display: "flex", flexDirection: "column", gap: 14 }}>

        {/* Customer info */}
        {customer ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div
                style={{
                  width: 42, height: 42, borderRadius: "50%", flexShrink: 0,
                  background: "linear-gradient(135deg, var(--accent-blue), var(--accent-violet))",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 18, boxShadow: "0 0 20px rgba(59,130,246,0.3)",
                }}
              >
                {customer.name?.[0] ?? "?"}
              </div>
              <div>
                <div style={{ fontWeight: 700, fontSize: 15 }}>
                  {customer.name ?? "Unknown Customer"}
                </div>
                <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
                  ID: {customer.customer_id ?? "—"}
                </div>
              </div>
              {customer.tier && (
                <div className={`badge ${tierColors[customer.tier] ?? "badge-blue"}`} style={{ marginLeft: "auto" }}>
                  {customer.tier}
                </div>
              )}
            </div>

            {/* Verification */}
            <div
              style={{
                display: "flex", alignItems: "center", gap: 8, padding: "8px 12px",
                borderRadius: "var(--radius-md)",
                background: customer.verified ? "rgba(16,185,129,0.08)" : "rgba(245,158,11,0.08)",
                border: `1px solid ${customer.verified ? "rgba(16,185,129,0.2)" : "rgba(245,158,11,0.2)"}`,
              }}
            >
              <Shield size={14} color={customer.verified ? "var(--accent-green)" : "var(--accent-amber)"} />
              <span style={{ fontSize: 12, color: customer.verified ? "var(--accent-green)" : "var(--accent-amber)", fontWeight: 600 }}>
                {customer.verified ? "Identity Verified" : "Unverified — verification required"}
              </span>
            </div>
          </div>
        ) : (
          <div style={{ color: "var(--text-muted)", fontSize: 12, textAlign: "center", padding: "12px 0" }}>
            No customer data yet
          </div>
        )}

        {/* Turn count & sentiment */}
        {conversation && (
          <div style={{ display: "flex", gap: 8 }}>
            <div className="metric-card" style={{ flex: 1, padding: 10 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <Clock size={12} color="var(--text-muted)" />
                <span className="metric-label">Turn</span>
              </div>
              <div className="metric-value" style={{ fontSize: 20, marginTop: 4 }}>
                {conversation.turn_count}
              </div>
            </div>
            <div className="metric-card" style={{ flex: 1, padding: 10 }}>
              <span className="metric-label">Sentiment</span>
              <div style={{ marginTop: 4, fontSize: 20 }}>
                {{ neutral: "😐", satisfied: "😊", frustrated: "😤", urgent: "🚨" }[conversation.sentiment] ?? "😐"}
              </div>
            </div>
          </div>
        )}

        {/* Active flags */}
        {activeFlags.length > 0 && (
          <div>
            <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
              Case Flags
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {activeFlags.map((flag) => {
                const cfg = flagLabels[flag];
                if (!cfg) return null;
                return (
                  <div key={flag} className={`badge ${cfg.color}`}>
                    {cfg.label}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Entities extracted */}
        {intent && Object.keys(intent.entities ?? {}).length > 0 && (
          <div>
            <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
              Collected Data
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {Object.entries(intent.entities).map(([k, v]) => (
                <div
                  key={k}
                  style={{
                    display: "flex", justifyContent: "space-between", alignItems: "center",
                    padding: "6px 10px", borderRadius: "var(--radius-sm)",
                    background: "rgba(6,182,212,0.06)", border: "1px solid rgba(6,182,212,0.15)",
                  }}
                >
                  <span style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "capitalize" }}>
                    {k.replace(/_/g, " ")}
                  </span>
                  <span className="font-mono text-xs" style={{ color: "var(--accent-cyan)" }}>{v}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
