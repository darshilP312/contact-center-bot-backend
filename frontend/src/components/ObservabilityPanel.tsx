import React from 'react';
import type { ServerObservability } from '../wsTypes';

interface Props { observability: ServerObservability | null; }

const STAGE_BUDGET: Record<string, number> = {
  understand: 150, plan: 200, execute: 200, respond: 300,
};

export const ObservabilityPanel: React.FC<Props> = ({ observability }) => {
  if (!observability) {
    return (
      <div className="obs-panel obs-panel--empty">
        <h4 className="obs-panel__title">📊 Observability</h4>
        <p className="obs-panel__empty">Metrics appear after the first turn.</p>
      </div>
    );
  }

  const total = Object.values(observability.stage_latencies_ms).reduce((a, b) => a + b, 0);
  const overBudget = total > 1200;

  return (
    <div className="obs-panel">
      <h4 className="obs-panel__title">📊 Turn {observability.turn} Metrics</h4>

      {/* Latency bars */}
      <div className="obs-latency">
        {Object.entries(observability.stage_latencies_ms).map(([stage, ms]) => {
          const budget = STAGE_BUDGET[stage] ?? 300;
          const pct = Math.min(100, (ms / budget) * 100);
          const over = ms > budget;
          return (
            <div key={stage} className="obs-latency__row">
              <span className="obs-latency__label">{stage}</span>
              <div className="obs-latency__bar-wrap">
                <div
                  className={`obs-latency__bar ${over ? 'obs-latency__bar--over' : ''}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className={`obs-latency__ms ${over ? 'obs-latency__ms--over' : ''}`}>
                {ms.toFixed(0)}ms
              </span>
            </div>
          );
        })}
        <div className={`obs-latency__total ${overBudget ? 'obs-latency__total--over' : ''}`}>
          Total: {total.toFixed(0)}ms {overBudget ? '⚠️ OVER BUDGET' : '✓'}
        </div>
      </div>

      {/* Token & cost */}
      <div className="obs-meta">
        <div className="obs-meta__item">
          <span className="obs-meta__label">Tokens</span>
          <span className="obs-meta__value">{observability.total_tokens.toLocaleString()}</span>
        </div>
        <div className="obs-meta__item">
          <span className="obs-meta__label">Cost</span>
          <span className="obs-meta__value">${observability.cost_usd.toFixed(4)}</span>
        </div>
        {observability.intent && (
          <div className="obs-meta__item obs-meta__item--full">
            <span className="obs-meta__label">Intent</span>
            <span className="obs-meta__value obs-meta__value--intent">{observability.intent}</span>
          </div>
        )}
      </div>

      {/* Tool calls */}
      {observability.tool_calls.length > 0 && (
        <div className="obs-tools">
          <span className="obs-tools__label">🔧 Tools:</span>
          {observability.tool_calls.map((t, i) => (
            <span key={i} className="obs-tools__tag">{t}</span>
          ))}
        </div>
      )}
    </div>
  );
};
