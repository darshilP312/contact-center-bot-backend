import { useRef, useCallback, useState } from "react";

const SAMPLE_RATE = 16000;
const CHUNK_INTERVAL_MS = 30; // 30ms PCM frames matching VAD frame size

interface UseVoiceStreamOptions {
  onAudioChunk: (chunk: ArrayBuffer) => void;
  onError?: (error: Error) => void;
}

export function useVoiceStream({ onAudioChunk, onError }: UseVoiceStreamOptions) {
  const [isRecording, setIsRecording] = useState(false);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: SAMPLE_RATE,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      mediaStreamRef.current = stream;

      const ctx = new AudioContext({ sampleRate: SAMPLE_RATE });
      audioCtxRef.current = ctx;

      const source = ctx.createMediaStreamSource(stream);
      sourceRef.current = source;

      // ScriptProcessorNode for capturing raw PCM
      // (AudioWorklet is preferred but requires HTTPS for mic access on some browsers)
      const bufferSize = 480; // 30ms @ 16kHz
      const processor = ctx.createScriptProcessor(bufferSize, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (event) => {
        const inputData = event.inputBuffer.getChannelData(0);
        // Convert float32 → int16 PCM
        const pcm16 = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          const clamped = Math.max(-1, Math.min(1, inputData[i]));
          pcm16[i] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
        }
        onAudioChunk(pcm16.buffer);
      };

      source.connect(processor);
      processor.connect(ctx.destination);

      setIsRecording(true);
    } catch (err) {
      const error = err instanceof Error ? err : new Error("Microphone access denied");
      onError?.(error);
    }
  }, [onAudioChunk, onError]);

  const stopRecording = useCallback(() => {
    processorRef.current?.disconnect();
    sourceRef.current?.disconnect();
    audioCtxRef.current?.close();
    mediaStreamRef.current?.getTracks().forEach((t) => t.stop());

    processorRef.current = null;
    sourceRef.current = null;
    audioCtxRef.current = null;
    mediaStreamRef.current = null;

    setIsRecording(false);
  }, []);

  return { isRecording, startRecording, stopRecording };
}
