import React, { useCallback, useRef, useState } from 'react';
import { AudioClient } from './AudioClient';
import { useConversationStore } from './store/conversationStore';
import { TranscriptPanel } from './components/TranscriptPanel';
import { WorkflowProgressPanel } from './components/WorkflowProgressPanel';
import { ObservabilityPanel } from './components/ObservabilityPanel';
import { Header } from './components/Header';
import type { ServerMessage } from './wsTypes';

const WS_URL = 'ws://localhost:8000';

export default function App() {
  const store = useConversationStore();
  const clientRef = useRef<AudioClient | null>(null);
  const [textInput, setTextInput] = useState('');
  const [isConnected, setIsConnected] = useState(false);

  const handleMessage = useCallback((msg: ServerMessage) => {
    switch (msg.type) {
      case 'transcript_partial':
        store.setPartialTranscript(msg.text);
        break;
      case 'transcript_final':
        store.addUserEntry(msg.text);
        break;
      case 'assistant_text':
        if (msg.is_streaming) {
          store.appendAssistantToken(msg.text);
        } else {
          store.finaliseAssistantEntry(msg.text, msg.rag_citations ?? []);
        }
        break;
      case 'state_update':
        store.applyStateUpdate(msg);
        break;
      case 'ticket':
        store.setTicket(msg);
        break;
      case 'policy_block':
        store.setPolicyBlock(msg);
        break;
      case 'observability':
        store.setObservability(msg);
        break;
    }
  }, [store]);

  const handleConnect = async () => {
    const client = new AudioClient(WS_URL, handleMessage, (s) => {
      store.setConnectionStatus(s);
      setIsConnected(s !== 'idle' && s !== 'disconnected');
    });
    clientRef.current = client;
    await client.connect(store.sessionId);
    setIsConnected(true);
  };

  const handleDisconnect = () => {
    clientRef.current?.disconnect();
    setIsConnected(false);
  };

  const handleSendText = (e: React.FormEvent) => {
    e.preventDefault();
    if (!textInput.trim() || !clientRef.current) return;
    clientRef.current.sendText(textInput.trim());
    setTextInput('');
  };

  const handleMicToggle = async () => {
    if (!clientRef.current) return;
    if (store.connectionStatus === 'recording') {
      clientRef.current.stopRecording();
    } else {
      await clientRef.current.startRecording();
    }
  };

  return (
    <div className="app">
      <Header
        connectionStatus={store.connectionStatus}
        sessionId={store.sessionId}
        sentiment={store.sentiment}
        customerTier={store.customerTier}
        onConnect={handleConnect}
        onDisconnect={handleDisconnect}
        isConnected={isConnected}
      />

      <main className="app__main">
        {/* Left: Transcript */}
        <section className="app__panel app__panel--transcript">
          <TranscriptPanel
            entries={store.entries}
            partialTranscript={store.partialTranscript}
            connectionStatus={store.connectionStatus}
          />

          {/* Text input for dev mode */}
          <form className="text-input-bar" onSubmit={handleSendText} id="text-input-form">
            <input
              id="text-input"
              type="text"
              className="text-input-bar__input"
              placeholder={isConnected ? "Type a message (dev mode)..." : "Connect to start..."}
              value={textInput}
              onChange={e => setTextInput(e.target.value)}
              disabled={!isConnected}
              autoComplete="off"
            />
            <button
              type="button"
              id="mic-toggle-btn"
              className={`text-input-bar__mic ${store.connectionStatus === 'recording' ? 'text-input-bar__mic--active' : ''}`}
              onClick={handleMicToggle}
              disabled={!isConnected}
              title={store.connectionStatus === 'recording' ? 'Stop recording' : 'Start recording'}
            >
              {store.connectionStatus === 'recording' ? '⏹' : '🎤'}
            </button>
            <button
              type="submit"
              id="send-text-btn"
              className="text-input-bar__send"
              disabled={!isConnected || !textInput.trim()}
            >
              Send
            </button>
          </form>
        </section>

        {/* Right: Workflow + Observability */}
        <aside className="app__panel app__panel--sidebar">
          <WorkflowProgressPanel
            workflowName={store.workflowName}
            currentStep={store.workflowStep}
            completedSteps={store.completedSteps}
            ticket={store.ticket}
            policyBlock={store.policyBlock}
            sentiment={store.sentiment}
            customerTier={store.customerTier}
          />
          <ObservabilityPanel observability={store.observability} />
        </aside>
      </main>
    </div>
  );
}
