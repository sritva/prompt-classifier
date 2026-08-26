import React, { useEffect, useState, useMemo } from "react";
import { useSession } from "./hooks/useSession";
import { Glyph } from "./components/Glyph";
import { StatsChart } from "./components/StatsChart";
import { PromptInputForm } from "./components/PromptInputForm";
import { OverrelianceBanner } from "./components/OverrelianceBanner";
import { CognitiveDetailModal } from "./components/CognitiveDetailModal";
import { HistoryList } from "./components/HistoryList";

export const App: React.FC = () => {
  const {
    history,
    summary,
    latestResult,
    selectedPrompt,
    setSelectedPrompt,
    loading,
    error,
    dismissedWarning,
    setDismissedWarning,
    submitPrompt,
    clearSession,
  } = useSession();

  const [showInfo, setShowInfo] = useState<boolean>(false);

  useEffect(() => {
    if (window.location.pathname !== "/") {
      document.title = "404 Not Found | Prompt Classifier";
    } else if (selectedPrompt) {
      document.title = `Analysis: "${selectedPrompt.prompt.substring(0, 20)}..." | Prompt Classifier`;
    } else if (latestResult) {
      document.title = `Result: ${latestResult.classification} | Prompt Classifier`;
    } else {
      document.title = "Prompt Classifier";
    }
  }, [selectedPrompt, latestResult]);

  const consecutiveConvergent = useMemo(() => {
    let count = 0;
    for (let i = history.length - 1; i >= 0; i--) {
      if (history[i].classification === "convergent") {
        count++;
      } else {
        break;
      }
    }
    return count;
  }, [history]);

  const actionableGuidance = useMemo(() => {
    if (!summary || summary.overreliance_signal === "none") return null;
    const recentSubtypes = history.slice(-5).map((h) => h.subtype);
    if (recentSubtypes.includes("decision_making")) {
      return "Brainstorm 3 independent options and write down their pros/cons before asking AI for a choice recommendation.";
    }
    if (recentSubtypes.includes("code_debugging")) {
      return "Inspect the stack trace and isolate a minimal reproducing test case before requesting a direct code solution.";
    }
    if (recentSubtypes.includes("computation")) {
      return "Estimate the calculation range manually to verify the magnitude of the result.";
    }
    return "Draft your own hypothesis first, then use AI to critique edge cases rather than accepting the initial answer.";
  }, [summary, history]);

  const glyphState = latestResult ? latestResult.classification : "neutral";

  const handleClearConfirm = async () => {
    if (!window.confirm("Are you sure you want to clear this session's history?")) {
      return;
    }
    await clearSession();
  };

  if (window.location.pathname !== "/") {
    return (
      <div className="app-container" style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "80vh", textAlign: "center" }}>
        <h1 style={{ fontSize: "4rem", color: "var(--color-divergent)", margin: "0 0 1rem 0" }}>404</h1>
        <h2 style={{ fontSize: "1.5rem", margin: "0 0 2rem 0" }}>cognitive path lost</h2>
        <p style={{ maxWidth: "400px", color: "var(--color-muted)", margin: "0 0 2rem 0", lineHeight: "1.6" }}>
          The link or route you followed does not exist in this cognitive space. Return to the dashboard to classify prompts.
        </p>
        <button 
          onClick={() => { window.location.href = "/"; }} 
          className="submit-btn" 
          style={{ alignSelf: "center" }}
        >
          Go to Dashboard
        </button>
      </div>
    );
  }

  return (
    <div className="app-container">
      <header className="app-header" id="app-header">
        <div className="app-title-group">
          <h1 className="app-title">prompt classifier</h1>
          <span className="app-subtitle">guilford cognitive tool</span>
        </div>
        <Glyph state={glyphState} />
      </header>

      <OverrelianceBanner
        summary={summary}
        dismissedWarning={dismissedWarning}
        onDismiss={() => setDismissedWarning(true)}
        actionableGuidance={actionableGuidance}
        latestReflectionPrompt={latestResult?.reflection_prompt}
        consecutiveConvergent={consecutiveConvergent}
      />

      {error && (
        <div className="error-banner" id="error-banner" aria-live="assertive">
          [ ERROR ]: {error}
        </div>
      )}

      <section className="info-section">
        <button 
          onClick={() => setShowInfo(!showInfo)} 
          className="info-toggle-btn"
          aria-expanded={showInfo}
        >
          {showInfo ? "[ Hide Guide & Cognitive Theory ]" : "[ Show Guide & Cognitive Theory ]"}
        </button>
        
        {showInfo && (
          <div className="info-content">
            <div className="info-grid">
              <div className="info-card">
                <h3>What is this tool?</h3>
                <p>
                  This dashboard is a cognitive assistant designed to monitor how you rely on AI. It analyzes the prompts you submit and groups them into two primary thinking styles:
                </p>
                <ul>
                  <li><strong className="state-convergent">Convergent (Focused)</strong>: Prompts that search for a single correct, logical, or verifiable answer (such as writing/debugging code, solving math problems, looking up facts, or making personal choices).</li>
                  <li><strong className="state-divergent">Divergent (Creative)</strong>: Prompts that expand outwards to generate open-ended ideas, alternatives, or creative drafts (such as brainstorming, outlining, or writing stories).</li>
                </ul>
              </div>
              <div className="info-card">
                <h3>The Risk of Overreliance</h3>
                <p>
                  Outsourcing your analytical tasks or personal choices to AI creates a risk of <strong>automation complacency</strong> (or <strong>automation bias</strong>) — the habit of blindly trusting machine-generated suggestions instead of engaging in active critical thinking.
                </p>
                <p>
                  <em>Or in simpler terms—</em> if you always rely on a GPS to navigate, you eventually forget how to read a map. Similarly, if you constantly offload your thinking to AI, you risk losing the habit of questioning things and solving complex problems on your own.
                </p>
                <p>
                  This tool tracks your prompt history inside a rolling <strong>10-minute window</strong> to calculate an <strong>Overreliance Score</strong>. If your score gets too high, the system alerts you and offers reflective challenge prompts to encourage independent reasoning.
                </p>
              </div>
            </div>
            
            <div className="scoring-table-wrapper">
              <h4>Overreliance Scoring Rules (10-Min Window)</h4>
              <table className="scoring-table">
                <thead>
                  <tr>
                    <th>Prompt Type</th>
                    <th>Points</th>
                    <th>Rationale</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td><strong>Making a Decision</strong></td>
                    <td style={{ color: "var(--color-divergent)", fontWeight: "bold" }}>+3 points</td>
                    <td>High risk: Offloads subjective, personal choice and critical judgment.</td>
                  </tr>
                  <tr>
                    <td><strong>Fixing Code</strong></td>
                    <td style={{ color: "var(--color-divergent)", fontWeight: "bold" }}>+2 points</td>
                    <td>Moderate risk: Bypasses the learning process of active debugging.</td>
                  </tr>
                  <tr>
                    <td><strong>Facts / Computation / Other</strong></td>
                    <td style={{ color: "var(--color-muted)" }}>+1 point</td>
                    <td>Low risk: Routine reference lookups.</td>
                  </tr>
                  <tr>
                    <td><strong>Creative / Brainstorming</strong></td>
                    <td style={{ color: "var(--color-convergent)", fontWeight: "bold" }}>-1 point</td>
                    <td>Score offset: Uses AI as a collaborative sounding board.</td>
                  </tr>
                </tbody>
              </table>
              <p className="scoring-note">
                Scores &ge; 5 trigger a warning banner, and &ge; 8 trigger a high-level warning. The minimum possible score is 0.
              </p>
            </div>

            <div className="research-references-section" style={{ borderTop: "1px solid var(--color-border)", paddingTop: "1.25rem", marginTop: "1rem" }}>
              <h4 style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem", margin: "0 0 0.75rem 0", textTransform: "uppercase", color: "var(--color-muted)" }}>
                Scientific Research References
              </h4>
              <ul style={{ margin: 0, paddingLeft: "1.25rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                <li style={{ fontSize: "0.85rem", lineHeight: "1.5" }}>
                  <strong>Guilford (1959)</strong>: Defined the difference between focused analytical thinking (convergent) and open-ended creative thinking (divergent).
                </li>
                <li style={{ fontSize: "0.85rem", lineHeight: "1.5" }}>
                  <strong>Parasuraman & Manzey (2010)</strong>: Showed that when automated systems are highly reliable, humans stop checking them, losing their own ability to solve the problems.
                </li>
              </ul>
            </div>
          </div>
        )}
      </section>

      <PromptInputForm
        onSubmit={async (p) => { await submitPrompt(p); }}
        loading={loading}
      />

      {latestResult && (
        <section className="result-card" id="latest-result">
          <div className="result-header">
            <span
              className={`result-badge ${
                latestResult.classification === "convergent"
                  ? "state-convergent"
                  : "state-divergent"
              }`}
            >
              {latestResult.classification}
              {latestResult.subtype && ` (${latestResult.subtype})`}
            </span>
            <span className="result-confidence">
              Confidence: {Math.round(latestResult.confidence * 100)}%
            </span>
          </div>
          <p className="result-reasoning">{latestResult.reasoning}</p>

          {latestResult.reflection_prompt && (
            <div className="result-reflection">
              <strong>Reflection Challenge:</strong> "{latestResult.reflection_prompt}"
            </div>
          )}

          {latestResult.explanation_details && (
            <div className="result-explanation-grid">
              <div className="explanation-meta-item">
                <span className="meta-label">Complexity:</span>
                <span className="meta-val">{latestResult.explanation_details.complexity}</span>
              </div>
              <div className="explanation-meta-item">
                <span className="meta-label">Factual Dependency:</span>
                <span className="meta-val">{latestResult.explanation_details.factual_dependency}</span>
              </div>
              <div className="explanation-meta-item">
                <span className="meta-label">Creative Freedom:</span>
                <span className="meta-val">{latestResult.explanation_details.creative_freedom_score}</span>
              </div>
            </div>
          )}
        </section>
      )}

      <CognitiveDetailModal
        selectedPrompt={selectedPrompt}
        onClose={() => setSelectedPrompt(null)}
      />

      {summary && summary.total_prompts > 0 && (
        <section className="stats-box" id="session-stats">
          <h2 className="history-title">session profile</h2>
          
          <div className="stats-grid">
            <div className="stat-item">
              <span className="stat-label">total prompts</span>
              <span className="stat-value">{summary.total_prompts}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">convergent</span>
              <span className="stat-value">{summary.convergent_percentage}%</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">divergent</span>
              <span className="stat-value">{summary.divergent_percentage}%</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">overreliance score</span>
              <span className="stat-value" style={{ 
                color: summary.overreliance_signal === "high" 
                  ? "var(--color-warning-border)" 
                  : summary.overreliance_signal === "moderate"
                  ? "var(--color-divergent)"
                  : "var(--color-text)"
              }}>
                {summary.overreliance_score}
              </span>
            </div>
          </div>

          <div className="trend-meter-container" style={{ margin: "1rem 0", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: "var(--color-muted)" }}>
              <span>Focused Convergent ({summary.convergent_percentage}%)</span>
              <span>Open Divergent ({summary.divergent_percentage}%)</span>
            </div>
            <div style={{ display: "flex", height: "8px", width: "100%", backgroundColor: "var(--color-border)", borderRadius: "4px", overflow: "hidden" }}>
              <div style={{ width: `${summary.convergent_percentage}%`, backgroundColor: "var(--color-convergent)", transition: "width 0.3s ease" }} />
              <div style={{ width: `${summary.divergent_percentage}%`, backgroundColor: "var(--color-divergent)", transition: "width 0.3s ease" }} />
            </div>
          </div>

          <div className="chart-container">
            <StatsChart history={history} />
          </div>
        </section>
      )}

      <HistoryList
        history={history}
        selectedPromptId={selectedPrompt?.id}
        onSelectPrompt={(item) => setSelectedPrompt(item)}
        onClear={handleClearConfirm}
      />

      <footer className="app-footer">
        <p className="footer-quote">
          "The real danger is not that computers will begin to think like men, but that men will begin to think like computers."
        </p>
        <span className="footer-author">— Sydney J. Harris</span>
        <div className="footer-meta">
          <span>© 2026 Prompt Classifier • <a href="https://github.com/sritva" target="_blank" rel="noreferrer">sritva</a></span>
          <span>•</span>
          <a href="/llms.txt" target="_blank" rel="noreferrer">llms.txt</a>
          <span>•</span>
          <a href="/sitemap.xml" target="_blank" rel="noreferrer">sitemap</a>
        </div>
      </footer>
    </div>
  );
};

export default App;
