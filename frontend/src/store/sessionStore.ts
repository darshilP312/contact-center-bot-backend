import { create } from "zustand";
import type {
  SessionState,
  ConversationState,
  CustomerInfo,
  IntentState,
  WorkflowState,
  SessionFlags,
  MetricsState,
} from "../api/types";

interface SessionStore {
  sessionId: string | null;
  domain: string;
  language: string;
  isConnected: boolean;
  connectionStatus: "idle" | "connecting" | "connected" | "reconnecting" | "disconnected" | "error";
  conversation: ConversationState | null;
  customer: CustomerInfo | null;
  intent: IntentState | null;
  workflow: WorkflowState | null;
  flags: SessionFlags | null;
  metrics: MetricsState | null;
  thinkingNodes: string[];
  lastError: string | null;
  escalated: boolean;

  // Actions
  setSessionId: (id: string) => void;
  setDomain: (domain: string) => void;
  setLanguage: (language: string) => void;
  setConnectionStatus: (status: SessionStore["connectionStatus"]) => void;
  updateFromSessionState: (state: Partial<SessionState>) => void;
  addThinkingNode: (node: string) => void;
  removeThinkingNode: (node: string) => void;
  setLastError: (error: string | null) => void;
  setEscalated: (val: boolean) => void;
  reset: () => void;
}

const DEFAULT_METRICS: MetricsState = {
  session_id: "",
  turn_latencies_ms: {},
  total_tokens_used: 0,
  total_cost: 0,
  tool_calls_made: 0,
};

export const useSessionStore = create<SessionStore>((set) => ({
  sessionId: null,
  domain: "insurance",
  language: "en",
  isConnected: false,
  connectionStatus: "idle",
  conversation: null,
  customer: null,
  intent: null,
  workflow: null,
  flags: null,
  metrics: DEFAULT_METRICS,
  thinkingNodes: [],
  lastError: null,
  escalated: false,

  setSessionId: (id) => set({ sessionId: id }),
  setDomain: (domain) => set({ domain }),
  setLanguage: (language) => set({ language }),

  setConnectionStatus: (status) =>
    set({
      connectionStatus: status,
      isConnected: status === "connected",
    }),

  updateFromSessionState: (state) =>
    set((prev) => ({
      conversation: state.conversation ?? prev.conversation,
      customer: state.customer ?? prev.customer,
      intent: state.intent ?? prev.intent,
      workflow: state.workflow ?? prev.workflow,
      flags: state.flags ?? prev.flags,
      metrics: state.metrics ?? prev.metrics,
    })),

  addThinkingNode: (node) =>
    set((prev) => ({
      thinkingNodes: prev.thinkingNodes.includes(node)
        ? prev.thinkingNodes
        : [...prev.thinkingNodes, node],
    })),

  removeThinkingNode: (node) =>
    set((prev) => ({
      thinkingNodes: prev.thinkingNodes.filter((n) => n !== node),
    })),

  setLastError: (error) => set({ lastError: error }),
  setEscalated: (val) => set({ escalated: val }),

  reset: () =>
    set({
      sessionId: null,
      isConnected: false,
      connectionStatus: "idle",
      conversation: null,
      customer: null,
      intent: null,
      workflow: null,
      flags: null,
      metrics: DEFAULT_METRICS,
      thinkingNodes: [],
      lastError: null,
      escalated: false,
    }),
}));
