import { create } from "zustand";
import type { MetricsUpdateEvent } from "../api/types";

interface MetricsStore {
  turnLatencies: number[];
  avgLatencyMs: number;
  lastTurnMs: number;
  totalTokens: number;
  totalCost: number;
  toolCallsMade: number;
  glassToGlassMs: number;

  updateMetrics: (event: MetricsUpdateEvent) => void;
  reset: () => void;
}

const calcAvg = (nums: number[]) =>
  nums.length === 0 ? 0 : Math.round(nums.reduce((a, b) => a + b, 0) / nums.length);

export const useMetricsStore = create<MetricsStore>((set) => ({
  turnLatencies: [],
  avgLatencyMs: 0,
  lastTurnMs: 0,
  totalTokens: 0,
  totalCost: 0,
  toolCallsMade: 0,
  glassToGlassMs: 0,

  updateMetrics: (event) =>
    set((prev) => {
      const latencies = Object.values(event.turn_latencies_ms ?? {});
      const lastLatency = latencies[latencies.length - 1] ?? prev.lastTurnMs;
      const allLatencies = [...prev.turnLatencies, lastLatency].slice(-20); // keep last 20

      return {
        turnLatencies: allLatencies,
        avgLatencyMs: calcAvg(allLatencies),
        lastTurnMs: lastLatency,
        totalTokens: event.total_tokens_used ?? prev.totalTokens,
        totalCost: event.total_cost ?? prev.totalCost,
        toolCallsMade: event.tool_calls_made ?? prev.toolCallsMade,
        glassToGlassMs: event.glass_to_glass_ms ?? prev.glassToGlassMs,
      };
    }),

  reset: () =>
    set({
      turnLatencies: [],
      avgLatencyMs: 0,
      lastTurnMs: 0,
      totalTokens: 0,
      totalCost: 0,
      toolCallsMade: 0,
      glassToGlassMs: 0,
    }),
}));
