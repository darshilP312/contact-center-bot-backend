import { useRef, useCallback, useEffect } from "react";
import { VoiceAIWebSocket } from "../api/websocket";
import { useSessionStore } from "../store/sessionStore";
import { useTranscriptStore } from "../store/transcriptStore";
import { useMetricsStore } from "../store/metricsStore";

export function useWebSocket(sessionId: string | null) {
  const wsRef = useRef<VoiceAIWebSocket | null>(null);
  const {
    domain,
    language,
    setConnectionStatus,
    updateFromSessionState,
    addThinkingNode,
    removeThinkingNode,
    setLastError,
    setEscalated,
  } = useSessionStore();
  const { addEntry, setPartialTranscript, clearPartial } = useTranscriptStore();
  const { updateMetrics } = useMetricsStore();

  const connect = useCallback(async () => {
    if (!sessionId) return;

    setConnectionStatus("connecting");
    const ws = new VoiceAIWebSocket(sessionId);
    wsRef.current = ws;

    // Register all event handlers BEFORE connecting
    ws.on("transcript.partial", ({ text }) => setPartialTranscript(text));

    ws.on("transcript.final", ({ text }) => {
      clearPartial();
      // Clear thinking nodes at start of each new turn
      [
        "conversation_understanding", "planner", "guardrails", "business_router",
        "rag", "tool_caller", "workflow_executor", "response_generator", "escalation_handler"
      ].forEach(node => removeThinkingNode(node));
      addEntry({ role: "customer", text, ts: new Date().toISOString() });
    });

    ws.on("agent.thinking", ({ node, status }) => {
      if (status === "running") addThinkingNode(node);
      else removeThinkingNode(node);
    });

    ws.on("intent.detected", (payload) => {
      updateFromSessionState({ intent: {
        session_id: sessionId,
        name: payload.name,
        confidence: payload.confidence,
        entities: payload.entities,
        secondary_intents: [],
      }});
    });

    ws.on("workflow.update", (payload) => {
      updateFromSessionState({ workflow: {
        session_id: sessionId,
        name: payload.workflow_name,
        step: payload.current_step,
        completed_steps: payload.completed_steps,
        step_results: {},
      }});
    });

    // Decision Engine planner output: intent_type + policy audit
    ws.on("planner.decision", (payload) => {
      // Merge intent_type into intent state
      const prev = useSessionStore.getState().intent;
      updateFromSessionState({
        intent: {
          session_id: sessionId,
          name: prev?.name,
          confidence: prev?.confidence ?? 0,
          entities: prev?.entities ?? {},
          secondary_intents: prev?.secondary_intents ?? [],
          intent_type: payload.intent_type,
        },
      });
    });

    ws.on("response.text", ({ text }) => {
      addEntry({ role: "agent", text, ts: new Date().toISOString() });
      clearPartial();
    });

    ws.on("session.state", (state) => {
      updateFromSessionState(state as never);
    });

    ws.on("session.escalated", () => {
      setEscalated(true);
    });

    ws.on("metrics.update", (event) => {
      updateMetrics(event);
    });

    ws.on("error", ({ message, recoverable }) => {
      setLastError(message);
      if (!recoverable) setConnectionStatus("error");
    });

    try {
      await ws.connect();
      setConnectionStatus("connected");
      ws.sendSessionStart(domain, language);
    } catch (err) {
      setConnectionStatus("error");
      setLastError("Failed to connect to AI backend");
    }
  }, [sessionId, domain, language]);

  const disconnect = useCallback(() => {
    wsRef.current?.disconnect();
    wsRef.current = null;
    setConnectionStatus("disconnected");
  }, []);

  const sendText = useCallback((text: string) => {
    wsRef.current?.sendTextMessage(text);
  }, []);

  const sendAudio = useCallback((chunk: ArrayBuffer) => {
    wsRef.current?.sendAudioChunk(chunk);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      wsRef.current?.disconnect();
    };
  }, []);

  return { connect, disconnect, sendText, sendAudio, ws: wsRef };
}
