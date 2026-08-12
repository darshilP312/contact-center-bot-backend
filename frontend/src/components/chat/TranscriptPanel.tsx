import React from "react";
import { FileText } from "lucide-react";
import { useTranscriptStore } from "../../store/transcriptStore";

export function TranscriptPanel() {
  const { entries, partialTranscript } = useTranscriptStore();

  return (
    <div className="glass-card flex flex-col" style={{ height: "100%" }}>
      <div className="section-header">
        <FileText size={14} className="icon" />
        <span>Live Transcript</span>
        <span style={{ marginLeft: "auto", color: "var(--text-muted)", fontSize: 10 }}>
          {entries.length} turns
        </span>
      </div>

      <div style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: "8px 0" }}>
        {entries.map((entry, idx) => (
          <div
            key={idx}
            style={{
              padding: "8px 16px",
              borderBottom: "1px solid rgba(255,255,255,0.03)",
              animation: "slide-up 0.2s ease-out",
            }}
          >
            <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  textTransform: "uppercase",
                  letterSpacing: "0.06em",
                  color: entry.role === "customer" ? "var(--accent-blue)" : "var(--accent-cyan)",
                  paddingTop: 2,
                  minWidth: 50,
                  flexShrink: 0,
                }}
              >
                {entry.role}
              </span>
              <span style={{ fontSize: 13, color: "var(--text-primary)", lineHeight: 1.6 }}>
                {entry.text}
              </span>
            </div>
          </div>
        ))}

        {/* Partial transcript */}
        {partialTranscript && (
          <div style={{ padding: "8px 16px", opacity: 0.7 }}>
            <div style={{ display: "flex", gap: 8 }}>
              <span style={{ fontSize: 10, fontWeight: 700, color: "var(--accent-blue)", textTransform: "uppercase", letterSpacing: "0.06em", minWidth: 50 }}>
                customer
              </span>
              <span style={{ fontSize: 13, color: "var(--text-secondary)", fontStyle: "italic" }}>
                {partialTranscript}…
              </span>
            </div>
          </div>
        )}

        {entries.length === 0 && !partialTranscript && (
          <div style={{ textAlign: "center", padding: "24px", color: "var(--text-muted)", fontSize: 12 }}>
            Transcript will appear here when the session starts
          </div>
        )}
      </div>
    </div>
  );
}
