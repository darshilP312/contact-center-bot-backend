import type {
  WSMessage,
  WebSocketMessageType,
  ThinkingEvent,
  IntentDetectedEvent,
  WorkflowUpdateEvent,
  ErrorEvent,
  MetricsUpdateEvent,
  SessionState,
  TranscriptEntry,
} from "./types";

type EventHandler<T> = (payload: T) => void;

interface WSEventMap {
  "transcript.partial": EventHandler<{ text: string; session_id: string }>;
  "transcript.final": EventHandler<{ text: string; session_id: string; turn_count: number }>;
  "agent.thinking": EventHandler<ThinkingEvent>;
  "intent.detected": EventHandler<IntentDetectedEvent>;
  "workflow.update": EventHandler<WorkflowUpdateEvent>;
  "response.text": EventHandler<{ text: string; is_final: boolean; rag_used: boolean; session_id: string }>;
  "session.state": EventHandler<Partial<SessionState>>;
  "session.escalated": EventHandler<Record<string, unknown>>;
  "metrics.update": EventHandler<MetricsUpdateEvent>;
  "error": EventHandler<ErrorEvent>;
}

type AnyHandler = EventHandler<unknown>;

const WS_RECONNECT_DELAY_MS = 2000;
const WS_MAX_RECONNECT_ATTEMPTS = 5;

export class VoiceAIWebSocket {
  private ws: WebSocket | null = null;
  private sessionId: string;
  private url: string;
  private handlers: Map<string, AnyHandler[]> = new Map();
  private reconnectAttempts = 0;
  private isIntentionallyClosed = false;
  public isConnected = false;

  constructor(sessionId: string, baseUrl?: string) {
    this.sessionId = sessionId;
    const host = baseUrl ?? (import.meta.env.VITE_WS_URL || `ws://${window.location.hostname}:8000`);
    this.url = `${host}/api/v1/ws/${sessionId}`;
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.url);
      this.ws.binaryType = "arraybuffer";

      this.ws.onopen = () => {
        this.isConnected = true;
        this.reconnectAttempts = 0;
        console.info(`[WS] Connected — session: ${this.sessionId}`);
        resolve();
      };

      this.ws.onerror = (event) => {
        console.error("[WS] Error:", event);
        reject(new Error("WebSocket connection failed"));
      };

      this.ws.onmessage = (event) => {
        if (typeof event.data === "string") {
          this._handleTextMessage(event.data);
        } else if (event.data instanceof ArrayBuffer) {
          this._handleBinaryMessage(event.data);
        }
      };

      this.ws.onclose = (event) => {
        this.isConnected = false;
        console.info(`[WS] Closed — code: ${event.code}`);
        if (!this.isIntentionallyClosed) {
          this._scheduleReconnect();
        }
      };
    });
  }

  private _handleTextMessage(data: string): void {
    try {
      const msg = JSON.parse(data) as WSMessage;
      const handlers = this.handlers.get(msg.type) ?? [];
      handlers.forEach((h) => h(msg.payload));
    } catch (e) {
      console.warn("[WS] Failed to parse message:", data);
    }
  }

  private _handleBinaryMessage(buffer: ArrayBuffer): void {
    // Audio bytes from TTS — dispatch as custom event for AudioContext
    const event = new CustomEvent("ws:audio", { detail: buffer });
    window.dispatchEvent(event);
  }

  private _scheduleReconnect(): void {
    if (this.reconnectAttempts >= WS_MAX_RECONNECT_ATTEMPTS) {
      console.error("[WS] Max reconnect attempts reached");
      return;
    }
    this.reconnectAttempts++;
    const delay = WS_RECONNECT_DELAY_MS * this.reconnectAttempts;
    console.info(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
    setTimeout(() => this.connect().catch(console.error), delay);
  }

  on<K extends keyof WSEventMap>(event: K, handler: WSEventMap[K]): () => void {
    const existing = this.handlers.get(event) ?? [];
    this.handlers.set(event, [...existing, handler as AnyHandler]);
    return () => this.off(event, handler);
  }

  off<K extends keyof WSEventMap>(event: K, handler: WSEventMap[K]): void {
    const existing = this.handlers.get(event) ?? [];
    this.handlers.set(event, existing.filter((h) => h !== (handler as AnyHandler)));
  }

  sendSessionStart(domain: string, language: string): void {
    this._sendJSON("session.start", { domain, language });
  }

  sendTextMessage(text: string): void {
    this._sendJSON("text.message", { text });
  }

  sendSessionEnd(): void {
    this._sendJSON("session.end", {});
  }

  sendAudioChunk(pcmBytes: ArrayBuffer): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(pcmBytes);
    }
  }

  private _sendJSON(type: WebSocketMessageType, payload: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, payload }));
    } else {
      console.warn("[WS] Attempted to send while not connected:", type);
    }
  }

  disconnect(): void {
    this.isIntentionallyClosed = true;
    this._sendJSON("session.end", {});
    this.ws?.close(1000, "User ended session");
    this.isConnected = false;
  }
}
