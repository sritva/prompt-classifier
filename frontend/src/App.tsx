import React, { useEffect, useState } from "react";
import {
  getOrCreateSessionId,
  resetSessionId,
  classifyPrompt,
  getSessionHistory,
  clearSessionHistory,
} from "./api";
import type { PromptRecord, SessionSummary } from "./types";
import { Glyph } from "./components/Glyph";
import { StatsChart } from "./components/StatsChart";

export const App: React.FC = () => {
  const [sessionId, setSessionId] = useState<string>("");
  const [prompt, setPrompt] = useState<string>("");
  const [history, setHistory] = useState<PromptRecord[]>([]);
  const [summary, setSummary] = useState<SessionSummary | null>(null);
  const [latestResult, setLatestResult] = useState<PromptRecord | null>(null);
  const [selectedPrompt, setSelectedPrompt] = useState<PromptRecord | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [dismissedWarning, setDismissedWarning] = useState<boolean>(false);
  const [showInfo, setShowInfo] = useState<boolean>(false);

  useEffect(() => {
    const initSession = async () => {
      try {
        const id = await getOrCreateSessionId();
        setSessionId(id);
        fetchHistory(id);
      } catch (err: any) {
        setError(err.message || "Failed to initialize secure session.");
      }
    };
    initSession();
  }, []);

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

  const fetchHistory = async (id: string) => {
    try {
      const data = await getSessionHistory(id);
      setHistory(data.history);
      setSummary(data.session_summary);
      if (data.history.length > 0) {
        setLatestResult(data.history[data.history.length - 1]);
      } else {
        setLatestResult(null);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load session history.");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const result = await classifyPrompt(prompt, sessionId);
      setLatestResult(result);
      setHistory((prev) => [...prev, result]);
      setSummary(result.session_summary);
      setPrompt("");
      if (result.session_summary.overreliance_signal !== "none") {
        setDismissedWarning(false);
      }
    } catch (err: any) {
      setError(err.message || "An unexpected error occurred during classification.");
    } finally {
      setLoading(false);
    }
  };

  const handleClear = async () => {
    if (!window.confirm("Are you sure you want to clear this session's history?")) {
      return;
    }
    try {
      await clearSessionHistory(sessionId);
      const newId = await resetSessionId();
      setSessionId(newId);
      setHistory([]);
      setSummary(null);
      setLatestResult(null);
      setSelectedPrompt(null);
      setDismissedWarning(false);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to clear session.");
    }
  };

  const consecutiveConvergent = React.useMemo(() => {
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

  const actionableGuidance = React.useMemo(() => {
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

  const glyphState = latestResult
    ? latestResult.classification
    : "neutral";

  const showWarning =
    summary &&
    (summary.overreliance_signal === "high" ||
      summary.overreliance_signal === "moderate") &&
    !dismissedWarning;

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
              onClick={() => setDismissedWarning(true)}
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
          {latestResult?.reflection_prompt && (
            <div className="banner-reflection-friction">
              <strong>Reflective Challenge:</strong> "{latestResult.reflection_prompt}"
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

      <main>
        <form onSubmit={handleSubmit} className="prompt-form" id="prompt-form">
          <div className="input-wrapper">
            <textarea
              className="prompt-textarea"
              id="prompt-textarea"
              placeholder="Submit a prompt to analyze thinking style..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              disabled={loading}
              aria-label="Prompt text input"
              required
            />
          </div>
          <button
            type="submit"
            className="submit-btn"
            id="submit-btn"
            disabled={loading || !prompt.trim()}
          >
            {loading ? "Analyzing..." : "Classify Prompt"}
          </button>
        </form>
      </main>

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

      {selectedPrompt && (
        <section className="details-card" id="selected-details">
          <div className="details-header-row">
            <h2 className="details-title">selected prompt analysis</h2>
            <button onClick={() => setSelectedPrompt(null)} className="close-details-btn">
              Back to Latest
            </button>
          </div>
          
          <div className="details-body">
            <p className="details-prompt-text">"{selectedPrompt.prompt}"</p>
            
            <div className="details-meta-grid">
              <div className="detail-field">
                <span className="detail-label">Classification</span>
                <span className={`detail-value badge ${selectedPrompt.classification}`}>
                  {selectedPrompt.classification}
                </span>
              </div>
              {selectedPrompt.subtype && (
                <div className="detail-field">
                  <span className="detail-label">Subtype / Domain</span>
                  <span className="detail-value">{selectedPrompt.subtype}</span>
                </div>
              )}
              <div className="detail-field">
                <span className="detail-label">Confidence</span>
                <span className="detail-value">{Math.round(selectedPrompt.confidence * 100)}%</span>
              </div>
              {selectedPrompt.latency_ms !== undefined && selectedPrompt.latency_ms !== null && (
                <div className="detail-field">
                  <span className="detail-label">Latency</span>
                  <span className="detail-value">{selectedPrompt.latency_ms} ms</span>
                </div>
              )}
              {selectedPrompt.total_tokens !== undefined && selectedPrompt.total_tokens !== null && (
                <div className="detail-field">
                  <span className="detail-label">Tokens Used</span>
                  <span className="detail-value">{selectedPrompt.total_tokens}</span>
                </div>
              )}
            </div>

            <p className="details-reasoning"><strong>Reasoning:</strong> {selectedPrompt.reasoning}</p>

            {selectedPrompt.reflection_prompt && (
              <div className="details-reflection-box">
                <span className="box-title">Tailored Reflection Challenge</span>
                <p className="box-content">"{selectedPrompt.reflection_prompt}"</p>
              </div>
            )}

            {selectedPrompt.explanation_details && (
              <div className="details-explanation-section">
                <h3 className="section-title">Structured Explanation Details</h3>
                <div className="explanation-grid">
                  <div className="explanation-field">
                    <span className="field-label">Complexity:</span>
                    <span className={`field-value val-${selectedPrompt.explanation_details.complexity}`}>
                      {selectedPrompt.explanation_details.complexity}
                    </span>
                  </div>
                  <div className="explanation-field">
                    <span className="field-label">Factual Dependency:</span>
                    <span className={`field-value val-${selectedPrompt.explanation_details.factual_dependency}`}>
                      {selectedPrompt.explanation_details.factual_dependency}
                    </span>
                  </div>
                  <div className="explanation-field">
                    <span className="field-label">Creative Freedom Score:</span>
                    <span className="field-value">
                      {selectedPrompt.explanation_details.creative_freedom_score}
                    </span>
                  </div>
                </div>

                {selectedPrompt.explanation_details.given_inputs && selectedPrompt.explanation_details.given_inputs.length > 0 && (
                  <div className="inputs-outputs-section">
                    <strong>Given Inputs:</strong>
                    <ul>
                      {selectedPrompt.explanation_details.given_inputs.map((inp, i) => (
                        <li key={i}>{inp}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {selectedPrompt.explanation_details.expected_outputs && selectedPrompt.explanation_details.expected_outputs.length > 0 && (
                  <div className="inputs-outputs-section">
                    <strong>Expected Outputs:</strong>
                    <ul>
                      {selectedPrompt.explanation_details.expected_outputs.map((out, i) => (
                        <li key={i}>{out}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        </section>
      )}

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

      {history.length > 0 && (
        <section className="history-section" id="history-section">
          <div className="history-header-row">
            <h2 className="history-title">session timeline</h2>
            <button onClick={handleClear} className="clear-btn" id="clear-btn">
              Reset Session
            </button>
          </div>

          <div className="history-feed">
            {[...history].reverse().map((item, index) => (
              <div
                key={item.id || index}
                className={`history-item ${item.classification} ${selectedPrompt?.id === item.id ? "selected" : ""}`}
                onClick={() => setSelectedPrompt(item)}
                style={{ cursor: "pointer" }}
              >
                <p className="history-prompt">"{item.prompt}"</p>
                <div className="history-meta">
                  <span
                    className={
                      item.classification === "convergent"
                        ? "state-convergent"
                        : "state-divergent"
                    }
                  >
                    {item.classification}
                    {item.subtype && `:${item.subtype}`}
                  </span>
                  <span>•</span>
                  <span>{Math.round(item.confidence * 100)}% confidence</span>
                  {item.latency_ms !== undefined && item.latency_ms !== null && (
                    <>
                      <span>•</span>
                      <span>{item.latency_ms}ms</span>
                    </>
                  )}
                  <span>•</span>
                  <span>
                    {new Date(item.created_at).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
                <p className="history-reasoning">{item.reasoning}</p>
              </div>
            ))}
          </div>
        </section>
      )}

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
