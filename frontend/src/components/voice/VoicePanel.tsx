import React from "react";
import { Mic, MicOff, Phone, PhoneOff } from "lucide-react";
import { useSessionStore } from "../../store/sessionStore";

interface VoicePanelProps {
  isRecording: boolean;
  onToggleRecording: () => void;
  onConnect: () => void;
  onDisconnect: () => void;
  partialTranscript: string;
}

export function VoicePanel({
  isRecording,
  onToggleRecording,
  onConnect,
  onDisconnect,
  partialTranscript,
}: VoicePanelProps) {
  const { connectionStatus, conversation } = useSessionStore();
  const isConnected = connectionStatus === "connected";

  const sentiment = conversation?.sentiment ?? "neutral";
  const sentimentEmoji = {
    neutral: "😐",
    satisfied: "😊",
    frustrated: "😤",
    urgent: "🚨",
  }[sentiment] ?? "😐";

  return (
    <div
      className="glass-card flex flex-col"
      style={{ padding: 20, gap: 20, height: "100%" }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 15 }}>Voice Input</div>
          <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
            Real-time PCM → STT → AI
          </div>
        </div>
        {isConnected && (
          <div className={`badge sentiment-${sentiment}`} style={{ background: "transparent", border: "none", gap: 6 }}>
            <span style={{ fontSize: 18 }}>{sentimentEmoji}</span>
            <span style={{ fontSize: 11, fontWeight: 600, textTransform: "capitalize" }}>{sentiment}</span>
          </div>
        )}
      </div>

      {/* Voice ring button */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, flex: 1, justifyContent: "center" }}>
        <div
          className={`voice-ring ${isRecording ? "recording" : ""}`}
          onClick={isConnected ? onToggleRecording : undefined}
          style={{ opacity: isConnected ? 1 : 0.4, cursor: isConnected ? "pointer" : "not-allowed" }}
          role="button"
          aria-label={isRecording ? "Stop recording" : "Start recording"}
        >
          <div className="voice-ring-inner">
            {isRecording ? (
              <MicOff size={28} color="white" />
            ) : (
              <Mic size={28} color="white" />
            )}
          </div>
        </div>

        {/* Voice wave */}
        {isRecording && (
          <div className="voice-wave flex items-center gap-1" style={{ height: 32 }}>
            {[...Array(7)].map((_, i) => (
              <span
                key={i}
                style={{
                  height: 6,
                  animationDelay: `${i * 0.1}s`,
                  background: `hsl(${210 + i * 10}, 80%, 60%)`,
                }}
              />
            ))}
          </div>
        )}

        <p style={{ fontSize: 12, color: "var(--text-muted)", textAlign: "center" }}>
          {isConnected
            ? isRecording
              ? "Recording… speak now"
              : "Press to start speaking"
            : "Connect a session to enable voice"}
        </p>
      </div>

      {/* Partial transcript preview */}
      {partialTranscript && (
        <div
          style={{
            padding: "10px 14px",
            borderRadius: "var(--radius-md)",
            background: "rgba(59,130,246,0.08)",
            border: "1px solid rgba(59,130,246,0.2)",
            fontSize: 13,
            color: "var(--text-secondary)",
            fontStyle: "italic",
            minHeight: 44,
          }}
        >
          <span style={{ color: "var(--text-muted)", fontSize: 10, display: "block", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.06em" }}>
            Listening…
          </span>
          {partialTranscript}
        </div>
      )}

      {/* Session control buttons */}
      <div style={{ display: "flex", gap: 8 }}>
        {!isConnected ? (
          <button className="btn btn-primary w-full" onClick={onConnect} id="btn-connect-session">
            <Phone size={16} />
            Start Session
          </button>
        ) : (
          <button className="btn btn-danger w-full" onClick={onDisconnect} id="btn-disconnect-session">
            <PhoneOff size={16} />
            End Session
          </button>
        )}
      </div>
    </div>
  );
}
