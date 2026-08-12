/**
 * AudioClient.ts — Microphone capture, WebSocket streaming, and chunked PCM playback.
 * Handles the complete bidirectional audio pipeline for the contact centre.
 */

import type { ClientMessage, ServerMessage } from './wsTypes';

export type SessionState = 'idle' | 'connecting' | 'connected' | 'recording' | 'playing' | 'disconnected';
export type MessageHandler = (msg: ServerMessage) => void;
export type StateChangeHandler = (state: SessionState) => void;

export class AudioClient {
  private ws: WebSocket | null = null;
  private audioContext: AudioContext | null = null;
  private mediaStream: MediaStream | null = null;
  private workletNode: AudioWorkletNode | null = null;
  private sequenceNumber = 0;
  private isRecording = false;
  private playbackQueue: AudioBuffer[] = [];
  private isPlaying = false;
  private currentSource: AudioBufferSourceNode | null = null;

  constructor(
    private readonly wsUrl: string,
    private readonly onMessage: MessageHandler,
    private readonly onStateChange: StateChangeHandler,
  ) {}

  // ── Connection ──────────────────────────────────────────────────────────────

  async connect(sessionId: string): Promise<void> {
    this.onStateChange('connecting');
    const url = `${this.wsUrl}/ws/${sessionId}`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.onStateChange('connected');
      this.send({ type: 'control', action: 'start', session_id: sessionId });
    };

    this.ws.onmessage = (event: MessageEvent) => {
      const msg: ServerMessage = JSON.parse(event.data as string);
      this.handleServerMessage(msg);
      this.onMessage(msg);
    };

    this.ws.onerror = () => {
      this.onStateChange('disconnected');
    };

    this.ws.onclose = () => {
      this.stopRecording();
      this.onStateChange('disconnected');
    };

    await this.initAudioContext();
  }

  disconnect(): void {
    this.stopRecording();
    this.ws?.close();
    this.audioContext?.close();
    this.ws = null;
    this.audioContext = null;
    this.onStateChange('disconnected');
  }

  // ── Recording ──────────────────────────────────────────────────────────────

  async startRecording(): Promise<void> {
    if (this.isRecording) return;
    if (!this.audioContext) await this.initAudioContext();

    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });

      const source = this.audioContext!.createMediaStreamSource(this.mediaStream);

      await this.audioContext!.audioWorklet.addModule('/audio-processor.js');
      this.workletNode = new AudioWorkletNode(this.audioContext!, 'audio-processor');

      this.workletNode.port.onmessage = (event: MessageEvent) => {
        if (event.data.type === 'audio-chunk') {
          this.sendAudioChunk(event.data.buffer as ArrayBuffer);
        }
      };

      source.connect(this.workletNode);
      this.isRecording = true;
      this.onStateChange('recording');
    } catch (err) {
      console.error('[AudioClient] Failed to start recording:', err);
      throw err;
    }
  }

  stopRecording(): void {
    if (!this.isRecording) return;
    this.isRecording = false;
    this.mediaStream?.getTracks().forEach(t => t.stop());
    this.workletNode?.disconnect();
    this.workletNode = null;
    this.mediaStream = null;
    this.send({ type: 'control', action: 'stop' });
    this.onStateChange('connected');
  }

  // ── Text input (dev mode) ─────────────────────────────────────────────────

  sendText(text: string): void {
    this.send({ type: 'text_input', text });
  }

  // ── Barge-in ──────────────────────────────────────────────────────────────

  interruptPlayback(): void {
    this.currentSource?.stop();
    this.playbackQueue = [];
    this.isPlaying = false;
    this.send({ type: 'control', action: 'barge_in' });
    this.onStateChange('connected');
  }

  // ── Server message handling ───────────────────────────────────────────────

  private async handleServerMessage(msg: ServerMessage): Promise<void> {
    if (msg.type === 'audio_chunk') {
      const buffer = base64ToArrayBuffer(msg.data);
      const audioBuffer = await this.decodeAudioChunk(buffer, msg.sample_rate);
      this.enqueuePlayback(audioBuffer);
    }
  }

  // ── Audio playback ────────────────────────────────────────────────────────

  private async decodeAudioChunk(buffer: ArrayBuffer, sampleRate: number): Promise<AudioBuffer> {
    const pcm16 = new Int16Array(buffer);
    const float32 = new Float32Array(pcm16.length);
    for (let i = 0; i < pcm16.length; i++) {
      float32[i] = pcm16[i] / 32768.0;
    }
    const audioBuffer = this.audioContext!.createBuffer(1, float32.length, sampleRate);
    audioBuffer.getChannelData(0).set(float32);
    return audioBuffer;
  }

  private enqueuePlayback(buffer: AudioBuffer): void {
    this.playbackQueue.push(buffer);
    if (!this.isPlaying) this.playNextChunk();
  }

  private playNextChunk(): void {
    if (this.playbackQueue.length === 0) {
      this.isPlaying = false;
      this.onStateChange('connected');
      return;
    }
    this.isPlaying = true;
    this.onStateChange('playing');
    const buffer = this.playbackQueue.shift()!;
    const source = this.audioContext!.createBufferSource();
    source.buffer = buffer;
    source.connect(this.audioContext!.destination);
    source.onended = () => this.playNextChunk();
    source.start();
    this.currentSource = source;
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  private async initAudioContext(): Promise<void> {
    this.audioContext = new AudioContext({ sampleRate: 16000 });
    if (this.audioContext.state === 'suspended') {
      await this.audioContext.resume();
    }
  }

  private sendAudioChunk(buffer: ArrayBuffer): void {
    const base64 = arrayBufferToBase64(buffer);
    this.send({ type: 'audio_chunk', seq: this.sequenceNumber++, data: base64, sample_rate: 16000 });
  }

  private send(msg: ClientMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }
}

// ── Utilities ─────────────────────────────────────────────────────────────────

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function base64ToArrayBuffer(base64: string): ArrayBuffer {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}
