import { create } from "zustand";
import type { TranscriptEntry } from "../api/types";

interface TranscriptStore {
  entries: TranscriptEntry[];
  partialTranscript: string;
  agentPartial: string;

  addEntry: (entry: TranscriptEntry) => void;
  setPartialTranscript: (text: string) => void;
  setAgentPartial: (text: string) => void;
  clearPartial: () => void;
  clear: () => void;
}

export const useTranscriptStore = create<TranscriptStore>((set) => ({
  entries: [],
  partialTranscript: "",
  agentPartial: "",

  addEntry: (entry) =>
    set((state) => ({
      entries: [...state.entries, entry],
    })),

  setPartialTranscript: (text) => set({ partialTranscript: text }),
  setAgentPartial: (text) => set({ agentPartial: text }),

  clearPartial: () => set({ partialTranscript: "", agentPartial: "" }),

  clear: () =>
    set({
      entries: [],
      partialTranscript: "",
      agentPartial: "",
    }),
}));
