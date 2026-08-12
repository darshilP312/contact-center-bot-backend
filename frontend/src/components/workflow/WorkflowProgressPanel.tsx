import React from "react";
import { GitBranch, CheckCircle2, Circle, Loader2 } from "lucide-react";
import { useSessionStore } from "../../store/sessionStore";

export function WorkflowProgressPanel() {
  const { workflow } = useSessionStore();

  if (!workflow?.name) {
    return (
      <div className="glass-card flex flex-col" style={{ height: "100%" }}>
        <div className="section-header">
          <GitBranch size={14} className="icon" />
          <span>Workflow Progress</span>
        </div>
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: 12, flexDirection: "column", gap: 8 }}>
          <GitBranch size={24} style={{ opacity: 0.3 }} />
          <span>No active workflow</span>
        </div>
      </div>
    );
  }

  const { name, step, completed_steps } = workflow;
  const allSteps = [...completed_steps, ...(step ? [step] : [])];
  const totalKnown = allSteps.length;
  const completedCount = completed_steps.length;
  const pct = totalKnown > 0 ? Math.round((completedCount / totalKnown) * 100) : 0;

  return (
    <div className="glass-card flex flex-col" style={{ height: "100%" }}>
      <div className="section-header">
        <GitBranch size={14} className="icon" />
        <span>Workflow Progress</span>
        <span style={{ marginLeft: "auto", color: "var(--accent-cyan)", fontWeight: 700 }}>{pct}%</span>
      </div>

      <div style={{ padding: "12px 16px", flex: 1, minHeight: 0, overflowY: "auto", display: "flex", flexDirection: "column", gap: 12 }}>

        {/* Workflow name */}
        <div>
          <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 6 }}>
            Active Workflow
          </div>
          <div className="badge badge-blue" style={{ fontSize: 13, padding: "6px 12px" }}>
            {name.replace(/_/g, " ")}
          </div>
        </div>

        {/* Progress bar */}
        <div>
          <div className="progress-bar" style={{ height: 6 }}>
            <div className="progress-fill" style={{ width: `${pct}%` }} />
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
            <span style={{ fontSize: 10, color: "var(--text-muted)" }}>{completedCount} completed</span>
            <span style={{ fontSize: 10, color: "var(--text-muted)" }}>{totalKnown} total</span>
          </div>
        </div>

        {/* Steps */}
        <div style={{ display: "flex", flexDirection: "column", gap: 4, flex: 1 }}>
          <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
            Steps
          </div>
          {completed_steps.map((s) => (
            <div key={s} className="workflow-step complete">
              <CheckCircle2 size={16} color="var(--accent-green)" style={{ flexShrink: 0 }} />
              <span style={{ fontSize: 12, color: "var(--text-secondary)", textDecoration: "line-through", opacity: 0.7 }}>
                {s.replace(/_/g, " ")}
              </span>
            </div>
          ))}
          {step && (
            <div className="workflow-step active">
              <Loader2 size={16} color="var(--accent-blue)" style={{ flexShrink: 0, animation: "spin 1s linear infinite" }} />
              <span style={{ fontSize: 12, color: "var(--text-primary)", fontWeight: 600 }}>
                {step.replace(/_/g, " ")}
              </span>
              <span className="badge badge-blue" style={{ marginLeft: "auto", fontSize: 10, padding: "2px 8px" }}>
                Active
              </span>
            </div>
          )}
          {!step && completedCount > 0 && (
            <div className="workflow-step complete" style={{ marginTop: 4 }}>
              <CheckCircle2 size={16} color="var(--accent-green)" style={{ flexShrink: 0 }} />
              <span style={{ fontSize: 12, color: "var(--accent-green)", fontWeight: 600 }}>
                Workflow Complete ✓
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
