import React from 'react';
import type { ServerTicket, ServerPolicyBlock } from '../wsTypes';

interface Props {
  workflowName: string | null;
  currentStep: string | null;
  completedSteps: string[];
  ticket: ServerTicket | null;
  policyBlock: ServerPolicyBlock | null;
  sentiment: string;
  customerTier: string | null;
}

const STEP_LABELS: Record<string, Record<string, string>> = {
  technical_support: {
    authenticate: 'Customer Identified', check_outage: 'Outage Checked',
    create_ticket_outage: 'Outage Ticket Created', run_diagnostics: 'Running Diagnostics',
    book_engineer: 'Engineer Booked', create_ticket: 'Ticket Created',
    escalate: 'Escalated to Human', confirm: 'Confirmed',
  },
  billing_refund: {
    authenticate: 'Customer Identified', lookup_invoice: 'Invoice Retrieved',
    verify_refund_eligibility: 'Eligibility Checked', explain_policy: 'Policy Explained',
    refund_payment: 'Refund Processed', send_confirmation: 'Confirmation Sent',
    create_ticket: 'Ticket Created', escalate: 'Escalated to Human', confirm: 'Confirmed',
  },
  policy_rag: {
    classify_query: 'Query Classified', authenticate: 'Customer Identified',
    retrieve_and_answer: 'Knowledge Retrieved', escalate: 'Escalated', confirm: 'Confirmed',
  },
};

const SENTIMENT_MAP: Record<string, { color: string; icon: string; label: string }> = {
  neutral:    { color: 'var(--c-neutral)',    icon: '😐', label: 'Neutral' },
  frustrated: { color: 'var(--c-warn)',       icon: '😤', label: 'Frustrated' },
  angry:      { color: 'var(--c-danger)',     icon: '😠', label: 'Angry' },
  satisfied:  { color: 'var(--c-success)',    icon: '😊', label: 'Satisfied' },
};

export const WorkflowProgressPanel: React.FC<Props> = ({
  workflowName, currentStep, completedSteps, ticket, policyBlock, sentiment, customerTier,
}) => {
  const stepLabels = workflowName ? (STEP_LABELS[workflowName] ?? {}) : {};
  const allStepIds = Object.keys(stepLabels);
  const sentimentInfo = SENTIMENT_MAP[sentiment] ?? SENTIMENT_MAP.neutral;

  const getStatus = (id: string) => {
    if (completedSteps.includes(id)) return 'completed';
    if (id === currentStep) return 'active';
    return 'pending';
  };

  return (
    <div className="workflow-panel">
      <div className="workflow-panel__header">
        <h3 className="workflow-panel__title">
          {workflowName
            ? workflowName.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
            : 'Awaiting Input'}
        </h3>
        {customerTier && (
          <span className={`tier-badge tier-badge--${customerTier}`}>
            {customerTier === 'premium' ? '⭐ Premium' : '● Standard'}
          </span>
        )}
      </div>

      {/* Sentiment */}
      <div className="sentiment-row" style={{ borderColor: sentimentInfo.color }}>
        <span>{sentimentInfo.icon}</span>
        <span style={{ color: sentimentInfo.color }}>{sentimentInfo.label}</span>
      </div>

      {/* Steps */}
      {allStepIds.length > 0 ? (
        <ol className="workflow-steps" aria-label="Workflow progress">
          {allStepIds.map((id, idx) => {
            const status = getStatus(id);
            return (
              <li key={id} className={`wf-step wf-step--${status}`} aria-label={`${stepLabels[id]}: ${status}`}>
                <div className="wf-step__indicator">
                  {status === 'completed' && <span className="wf-step__check">✓</span>}
                  {status === 'active' && <span className="wf-step__pulse" />}
                  {status === 'pending' && <span className="wf-step__num">{idx + 1}</span>}
                </div>
                <span className="wf-step__label">{stepLabels[id]}</span>
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="workflow-panel__empty">Workflow will appear when conversation starts.</p>
      )}

      {/* Ticket badge */}
      {ticket && (
        <div className="ticket-badge" id="ticket-badge" role="status" aria-label={`Ticket ${ticket.id} created`}>
          <span className="ticket-badge__icon">🎫</span>
          <div>
            <div className="ticket-badge__id">{ticket.id}</div>
            <div className="ticket-badge__type">{ticket.ticket_type}</div>
          </div>
        </div>
      )}

      {/* Policy alert */}
      {policyBlock && (
        <div className="policy-alert" role="alert" aria-label="Policy block active">
          <span>🛡️</span>
          <div>
            <div className="policy-alert__title">Policy Gate Active</div>
            <div className="policy-alert__msg">{policyBlock.rule}</div>
          </div>
        </div>
      )}
    </div>
  );
};
