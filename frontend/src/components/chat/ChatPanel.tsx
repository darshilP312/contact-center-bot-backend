import React, { useState, useRef, useEffect } from "react";
import { Send } from "lucide-react";
import { useTranscriptStore } from "../../store/transcriptStore";
import type { TranscriptEntry } from "../../api/types";

interface ChatPanelProps {
  onSendMessage: (text: string) => void;
  isConnected: boolean;
}

export function ChatPanel({ onSendMessage, isConnected }: ChatPanelProps) {
  const [inputText, setInputText] = useState("");
  const { entries } = useTranscriptStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries]);

  const handleSend = () => {
    const text = inputText.trim();
    if (!text || !isConnected) return;
    onSendMessage(text);
    setInputText("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const formatTime = (ts: string) => {
    try {
      return new Date(ts).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "";
    }
  };

  return (
    <div className="glass-card" style={{ height: "100%" }}>
      {/* Header */}
      <div className="section-header">
        <span>💬</span>
        <span>Text Chat</span>
        <span style={{ marginLeft: "auto", color: "var(--text-muted)", fontSize: 10 }}>
          {entries.filter((e) => e.role !== "system").length} messages
        </span>
      </div>

      {/* Messages area — flex: 1 + min-height: 0 makes it scrollable */}
      <div
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: "auto",
          padding: "12px 0",
          display: "flex",
          flexDirection: "column",
          gap: 4,
        }}
      >
        {entries.length === 0 && (
          <div style={{ textAlign: "center", color: "var(--text-muted)", padding: "40px 20px", fontSize: 13 }}>
            <div style={{ fontSize: 32, marginBottom: 12 }}>🎙️</div>
            <div style={{ fontWeight: 600, marginBottom: 6 }}>Start a conversation</div>
            <div>Use voice input above or type a message below</div>
          </div>
        )}

        {entries.map((entry: TranscriptEntry, idx: number) => (
          <div
            key={idx}
            style={{
              padding: "4px 16px",
              display: "flex",
              flexDirection: entry.role === "customer" ? "row-reverse" : "row",
              alignItems: "flex-end",
              gap: 8,
              animation: "slide-up 0.2s ease-out",
            }}
          >
            {/* Avatar */}
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: "50%",
                background: entry.role === "customer"
                  ? "linear-gradient(135deg, var(--accent-blue), #6366f1)"
                  : "linear-gradient(135deg, var(--accent-cyan), var(--accent-green))",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 12,
                flexShrink: 0,
              }}
            >
              {entry.role === "customer" ? "👤" : "🤖"}
            </div>

            {/* Bubble */}
            <div
              style={{
                maxWidth: "78%",
                padding: "10px 14px",
                borderRadius: 12,
                borderBottomRightRadius: entry.role === "customer" ? 4 : 12,
                borderBottomLeftRadius: entry.role === "agent" ? 4 : 12,
                background: entry.role === "customer"
                  ? "linear-gradient(135deg, rgba(59,130,246,0.25), rgba(99,102,241,0.2))"
                  : "rgba(255,255,255,0.04)",
                border: `1px solid ${entry.role === "customer" ? "rgba(59,130,246,0.25)" : "var(--border)"}`,
                fontSize: 13,
                lineHeight: 1.6,
                color: "var(--text-primary)",
              }}
            >
              <div>{entry.text}</div>
              <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 4, textAlign: "right" }}>
                {formatTime(entry.ts)}
                {entry.rag_citations && entry.rag_citations.length > 0 && (
                  <span style={{ marginLeft: 8, color: "var(--accent-cyan)" }}>
                    📚 {entry.rag_citations.join(", ")}
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input — pinned to bottom */}
      <div
        style={{
          padding: "12px 16px",
          borderTop: "1px solid var(--border)",
          display: "flex",
          gap: 8,
          alignItems: "flex-end",
          flexShrink: 0,
        }}
      >
        <textarea
          id="chat-input"
          className="input"
          style={{ resize: "none", height: 42, overflow: "hidden", lineHeight: 1.5 }}
          placeholder={isConnected ? "Type a message… (Enter to send)" : "Connect a session to chat"}
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={!isConnected}
          rows={1}
        />
        <button
          id="btn-send-message"
          className="btn btn-primary btn-icon"
          onClick={handleSend}
          disabled={!isConnected || !inputText.trim()}
          aria-label="Send message"
        >
          <Send size={16} />
        </button>
      </div>
    </div>
  );
}
