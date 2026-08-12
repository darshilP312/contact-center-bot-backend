/**
 * conversationStore.ts — Zustand state store for the UI.
 * Single source of truth for all UI state derived from WebSocket events.
 */

import { create } from 'zustand';
import type {
  ServerStateUpdate, ServerTicket, ServerPolicyBlock,
  ServerObservability, RagCitation,
} from '../wsTypes';

export interface TranscriptEntry {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  isStreaming: boolean;
  citations: RagCitation[];
  timestamp: Date;
}

export interface ConversationStore {
  // Connection
  sessionId: string;
  connectionStatus: 'idle' | 'connecting' | 'connected' | 'recording' | 'playing' | 'disconnected';

  // Transcript
  entries: TranscriptEntry[];
  partialTranscript: string;

  // Workflow
  workflowName: string | null;
  workflowStep: string | null;
  completedSteps: string[];
  flags: ServerStateUpdate['flags'];

  // Metadata
  sentiment: string;
  customerTier: string | null;
  ticket: ServerTicket | null;
  policyBlock: ServerPolicyBlock | null;
  observability: ServerObservability | null;

  // Actions
  setConnectionStatus: (s: ConversationStore['connectionStatus']) => void;
  setPartialTranscript: (text: string) => void;
  addUserEntry: (text: string) => void;
  addAssistantEntry: (text: string, citations?: RagCitation[]) => void;
  appendAssistantToken: (token: string) => void;
  finaliseAssistantEntry: (fullText: string, citations: RagCitation[]) => void;
  applyStateUpdate: (update: ServerStateUpdate) => void;
  setTicket: (ticket: ServerTicket) => void;
  setPolicyBlock: (block: ServerPolicyBlock) => void;
  setObservability: (obs: ServerObservability) => void;
  reset: () => void;
}

let _entryCounter = 0;
const newId = () => `entry_${++_entryCounter}_${Date.now()}`;

const defaultFlags: ServerStateUpdate['flags'] = {
  ticket_created: false,
  engineer_booked: false,
  escalated: false,
  awaiting_approval: false,
  refund_triggered: false,
  rag_used: false,
  barge_in_detected: false,
};

export const useConversationStore = create<ConversationStore>((set, get) => ({
  sessionId: `sess_${Math.random().toString(36).slice(2, 10)}`,
  connectionStatus: 'idle',
  entries: [],
  partialTranscript: '',
  workflowName: null,
  workflowStep: null,
  completedSteps: [],
  flags: defaultFlags,
  sentiment: 'neutral',
  customerTier: null,
  ticket: null,
  policyBlock: null,
  observability: null,

  setConnectionStatus: (s) => set({ connectionStatus: s }),
  setPartialTranscript: (text) => set({ partialTranscript: text }),

  addUserEntry: (text) => set(state => ({
    partialTranscript: '',
    entries: [...state.entries, {
      id: newId(), role: 'user', text, isStreaming: false, citations: [], timestamp: new Date(),
    }],
  })),

  addAssistantEntry: (text, citations = []) => set(state => ({
    entries: [...state.entries, {
      id: newId(), role: 'assistant', text, isStreaming: false, citations, timestamp: new Date(),
    }],
  })),

  appendAssistantToken: (token) => {
    const entries = get().entries;
    const last = entries[entries.length - 1];
    if (last?.role === 'assistant' && last.isStreaming) {
      set({ entries: [...entries.slice(0, -1), { ...last, text: last.text + token }] });
    } else {
      set({ entries: [...entries, {
        id: newId(), role: 'assistant', text: token, isStreaming: true, citations: [], timestamp: new Date(),
      }] });
    }
  },

  finaliseAssistantEntry: (fullText, citations) => {
    const entries = get().entries;
    const last = entries[entries.length - 1];
    if (last?.role === 'assistant') {
      set({ entries: [...entries.slice(0, -1), { ...last, text: fullText, isStreaming: false, citations }] });
    }
  },

  applyStateUpdate: (update) => set({
    workflowName: update.workflow_name,
    workflowStep: update.workflow_step,
    completedSteps: update.completed_steps,
    flags: update.flags,
    sentiment: update.sentiment,
    customerTier: update.customer_tier,
  }),

  setTicket: (ticket) => set({ ticket }),
  setPolicyBlock: (block) => set({ policyBlock: block }),
  setObservability: (obs) => set({ observability: obs }),

  reset: () => set({
    entries: [],
    partialTranscript: '',
    workflowName: null,
    workflowStep: null,
    completedSteps: [],
    flags: defaultFlags,
    sentiment: 'neutral',
    customerTier: null,
    ticket: null,
    policyBlock: null,
    observability: null,
  }),
}));
