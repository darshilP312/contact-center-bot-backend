import type { Domain, SessionState } from "./types";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

async function _fetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errorData.detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// ── Session Management ──────────────────────────────────────────────────────

export interface CreateSessionParams {
  domain: string;
  language?: string;
  channel?: "voice" | "chat" | "hybrid";
}

export interface CreateSessionResponse {
  session_id: string;
  created_at: string;
  domain: string;
  language: string;
  channel: string;
}

export const createSession = (params: CreateSessionParams): Promise<CreateSessionResponse> =>
  _fetch<CreateSessionResponse>("/sessions", {
    method: "POST",
    body: JSON.stringify({ channel: "voice", language: "en", ...params }),
  });

export const getSession = (sessionId: string): Promise<SessionState> =>
  _fetch<SessionState>(`/sessions/${sessionId}`);

export const deleteSession = (sessionId: string): Promise<{ session_id: string; ended_at: string }> =>
  _fetch(`/sessions/${sessionId}`, { method: "DELETE" });

export const getTranscript = (
  sessionId: string
): Promise<{ session_id: string; entries: unknown[] }> =>
  _fetch(`/sessions/${sessionId}/transcript`);

export const getMetrics = (
  sessionId: string
): Promise<{
  session_id: string;
  turn_latencies_ms: Record<string, number>;
  total_tokens_used: number;
  total_cost: number;
  tool_calls_made: number;
}> => _fetch(`/sessions/${sessionId}/metrics`);

// ── Domains ─────────────────────────────────────────────────────────────────

export const getDomains = (): Promise<{ domains: Domain[] }> =>
  _fetch<{ domains: Domain[] }>("/domains");

// ── Health ───────────────────────────────────────────────────────────────────

export const getHealth = (): Promise<{ status: string; timestamp: string }> =>
  _fetch("/health");

export const getReadiness = (): Promise<{
  status: string;
  checks: { name: string; status: string; detail?: string }[];
}> => _fetch("/ready");
