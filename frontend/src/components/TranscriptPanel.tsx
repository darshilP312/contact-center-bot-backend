import React, { useEffect, useRef } from 'react';
import type { TranscriptEntry } from '../store/conversationStore';
import type { RagCitation } from '../wsTypes';

interface Props {
  entries: TranscriptEntry[];
  partialTranscript: string;
  connectionStatus: string;
}

export const TranscriptPanel: React.FC<Props> = ({ entries, partialTranscript, connectionStatus }) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [entries, partialTranscript]);

  return (
    <div className="transcript-panel" role="log" aria-live="polite" aria-label="Conversation transcript">
      <div className={`conn-badge conn-badge--${connectionStatus}`} id="connection-status">
        <span className="conn-badge__dot" />
        <span className="conn-badge__label">
          {connectionStatus === 'connected' ? 'Connected'
            : connectionStatus === 'recording' ? 'Listening...'
            : connectionStatus === 'playing' ? 'Speaking...'
            : connectionStatus === 'connecting' ? 'Connecting...'
            : 'Disconnected'}
        </span>
      </div>

      <div className="transcript-messages">
        {entries.length === 0 && (
          <div className="transcript-empty">
            <span className="transcript-empty__icon">💬</span>
            <p>Connect and start speaking or type a message to begin.</p>
          </div>
        )}

        {entries.map(entry => (
          <MessageBubble key={entry.id} entry={entry} />
        ))}

        {partialTranscript && (
          <div className="message message--user message--partial">
            <span className="message__avatar">👤</span>
            <div className="message__bubble">
              <span className="message__text">{partialTranscript}</span>
              <span className="message__cursor" aria-hidden="true">|</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
};

const MessageBubble: React.FC<{ entry: TranscriptEntry }> = ({ entry }) => {
  const isUser = entry.role === 'user';
  return (
    <div className={`message message--${entry.role} ${entry.isStreaming ? 'message--streaming' : ''}`}>
      <span className="message__avatar">{isUser ? '👤' : '🤖'}</span>
      <div className="message__content">
        <div className="message__bubble">
          <span className="message__text">{entry.text}</span>
          {entry.isStreaming && <span className="message__typing-dot" aria-hidden="true" />}
        </div>
        {entry.citations.length > 0 && (
          <div className="citations" aria-label="Sources">
            <span className="citations__label">📚 Sources:</span>
            {entry.citations.map((c, i) => <CitationTag key={i} citation={c} />)}
          </div>
        )}
        <time className="message__time" dateTime={entry.timestamp.toISOString()}>
          {entry.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </time>
      </div>
    </div>
  );
};

const CitationTag: React.FC<{ citation: RagCitation }> = ({ citation }) => (
  <div className="citation-tag" title={citation.chunk}>
    <span className="citation-tag__icon">📄</span>
    <span className="citation-tag__source">
      {citation.source.replace('.txt', '').replace(/_/g, ' ')}
    </span>
    {citation.score > 0 && (
      <span className="citation-tag__score">{(citation.score * 100).toFixed(0)}%</span>
    )}
  </div>
);
