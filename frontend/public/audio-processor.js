/**
 * audio-processor.js — AudioWorklet processor for low-latency mic capture.
 * Runs on a dedicated audio thread. Sends 320-sample chunks (20ms at 16kHz).
 * Must be in /public so it can be loaded via audioContext.audioWorklet.addModule().
 */

class AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buffer = [];
    this._chunkSize = 320; // 20ms at 16kHz
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const samples = input[0]; // Float32Array

    // Convert Float32 to Int16 PCM
    for (let i = 0; i < samples.length; i++) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      this._buffer.push(s < 0 ? s * 0x8000 : s * 0x7fff);
    }

    // Send chunks when buffer is full
    while (this._buffer.length >= this._chunkSize) {
      const chunk = this._buffer.splice(0, this._chunkSize);
      const int16 = new Int16Array(chunk);
      this.port.postMessage({
        type: 'audio-chunk',
        buffer: int16.buffer,
      }, [int16.buffer]);
    }

    return true; // Keep processor alive
  }
}

registerProcessor('audio-processor', AudioProcessor);
