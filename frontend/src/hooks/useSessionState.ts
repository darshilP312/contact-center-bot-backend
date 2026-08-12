import { useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { createSession, deleteSession, getDomains } from "../api/rest";
import { useSessionStore } from "../store/sessionStore";
import { useTranscriptStore } from "../store/transcriptStore";
import { useMetricsStore } from "../store/metricsStore";

export function useSessionState() {
  const { sessionId, domain, language, setSessionId, setDomain, reset } = useSessionStore();
  const { clear: clearTranscript } = useTranscriptStore();
  const { reset: resetMetrics } = useMetricsStore();

  const { data: domainsData } = useQuery({
    queryKey: ["domains"],
    queryFn: getDomains,
    staleTime: 60_000,
  });

  const startNewSession = useCallback(async () => {
    const response = await createSession({ domain, language, channel: "voice" });
    setSessionId(response.session_id);
    return response.session_id;
  }, [domain, language, setSessionId]);

  const endSession = useCallback(async () => {
    if (sessionId) {
      await deleteSession(sessionId).catch(() => {}); // Best-effort
    }
    reset();
    clearTranscript();
    resetMetrics();
  }, [sessionId, reset, clearTranscript, resetMetrics]);

  return {
    sessionId,
    domain,
    language,
    domains: domainsData?.domains ?? [],
    setDomain,
    startNewSession,
    endSession,
  };
}
