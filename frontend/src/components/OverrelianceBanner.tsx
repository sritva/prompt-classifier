import React from "react";
import type { SessionSummary } from "../types";

interface OverrelianceBannerProps {
  summary: SessionSummary | null;
  dismissedWarning: boolean;
  onDismiss: () => void;
  actionableGuidance: string | null;
  latestReflectionPrompt?: string | null;
  consecutiveConvergent: number;
}

export const OverrelianceBanner: React.FC<OverrelianceBannerProps> = ({
  summary,
  dismissedWarning,
  onDismiss,
  actionableGuidance,
  latestReflectionPrompt,
  consecutiveConvergent,
}) => {
  const showWarning =
    summary &&
    (summary.overreliance_signal === "high" ||
      summary.overreliance_signal === "moderate") &&
    !dismissedWarning;

  return (
    <>
      {showWarning && summary && (
        <section
          className="overreliance-banner"
          id="overreliance-banner"
          aria-live="polite"
        >
          <div className="banner-header">
            <span className="banner-title">
              WARNING: COGNITIVE OVERRELIANCE ({summary.overreliance_signal.toUpperCase()})
            </span>
            <button
              onClick={onDismiss}
              className="banner-dismiss-btn"
              aria-label="Dismiss overreliance warning"
            >
              dismiss
            </button>
          </div>
          <p className="banner-body">
            You have submitted multiple convergent prompts in the last 10 minutes (Score: {summary.overreliance_score}). 
            HCI cognitive research demonstrates that automating analytical judgment risks automation bias.
          </p>
          {actionableGuidance && (
            <div className="banner-guidance" style={{ borderLeft: "3px solid var(--color-warning-border)", paddingLeft: "0.75rem", marginTop: "0.5rem" }}>
              <strong>Recommended Action:</strong> {actionableGuidance}
            </div>
          )}
          {latestReflectionPrompt && (
            <div className="banner-reflection-friction">
              <strong>Reflective Challenge:</strong> "{latestReflectionPrompt}"
            </div>
          )}
        </section>
      )}

      {consecutiveConvergent >= 3 && !dismissedWarning && (
        <section className="nudge-banner" id="progressive-nudge" style={{ backgroundColor: "#201D1A", border: "1px solid #7D5A2B", padding: "1rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem", color: "#D49B55", textTransform: "uppercase", fontWeight: "bold" }}>
              Progressive Reflection Nudge ({consecutiveConvergent} consecutive convergent queries)
            </span>
          </div>
          <p style={{ margin: 0, fontSize: "0.9rem", color: "var(--color-text)", lineHeight: "1.4" }}>
            Notice the streak of focused tasks. Try asking a divergent or exploratory question to balance your cognitive workflow.
          </p>
        </section>
      )}
    </>
  );
};
