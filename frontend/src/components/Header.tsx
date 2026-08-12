import React from 'react';

interface Props {
  connectionStatus: string;
  sessionId: string;
  sentiment: string;
  customerTier: string | null;
  onConnect: () => void;
  onDisconnect: () => void;
  isConnected: boolean;
}

export const Header: React.FC<Props> = ({
  sessionId, customerTier,
  onConnect, onDisconnect, isConnected,
}) => (
  <header className="header">
    <div className="header__brand">
      <span className="header__logo">⚡</span>
      <div>
        <h1 className="header__title">AI Contact Centre</h1>
        <p className="header__subtitle">Enterprise Orchestration Layer</p>
      </div>
    </div>

    <div className="header__meta">
      {sessionId && (
        <span className="header__session" title="Session ID">
          🔑 {sessionId}
        </span>
      )}
      {customerTier && (
        <span className={`header__tier header__tier--${customerTier}`}>
          {customerTier === 'premium' ? '⭐ Premium' : 'Standard'}
        </span>
      )}
    </div>

    <div className="header__actions">
      <button
        id="connect-btn"
        className={`btn ${isConnected ? 'btn--danger' : 'btn--primary'}`}
        onClick={isConnected ? onDisconnect : onConnect}
        aria-label={isConnected ? 'Disconnect session' : 'Connect to AI Contact Centre'}
      >
        {isConnected ? '⏹ Disconnect' : '▶ Connect'}
      </button>
    </div>
  </header>
);
