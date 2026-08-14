import React, { useEffect, useState } from "react";
import {
  getOrCreateSessionId,
  resetSessionId,
  classifyPrompt,
  getSessionHistory,
  clearSessionHistory,
} from "./api";
import { PromptRecord, SessionSummary } from "./types";
import { Glyph } from "./components/Glyph";
import { StatsChart } from "./components/StatsChart";

export const App: React.FC = () => {
  const [sessionId, setSessionId] = useState<string>("");
  const [prompt, setPrompt] = useState<string>("");
  const [history, setHistory] = useState<PromptRecord[]>([]);
  const [summary, setSummary] = useState<SessionSummary | null>(null);
  const [latestResult, setLatestResult] = useState<PromptRecord | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [dismissedWarning, setDismissedWarning] = useState<boolean>(false);

  // Initialize session
  useEffect(() => {
    const id = getOrCreateSessionId();
    setSessionId(id);
    fetchHistory(id);
  }, []);

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
      // Reset dismiss banner state if a new high/moderate signal occurs
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
      const newId = resetSessionId();
      setSessionId(newId);
      setHistory([]);
      setSummary(null);
      setLatestResult(null);
      setDismissedWarning(false);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to clear session.");
    }
  };

  // Determine current glyph state
  const glyphState = latestResult
    ? latestResult.classification
    : "neutral";

  // Check if warning banner should show
  const showWarning =
    summary &&
    (summary.overreliance_signal === "high" ||
      summary.overreliance_signal === "moderate") &&
    !dismissedWarning;

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header" id="app-header">
        <div className="app-title-group">
          <h1 className="app-title">prompt classifier</h1>
          <span className="app-subtitle">guilford cognitive tool</span>
        </div>
        <Glyph state={glyphState} />
      </header>

      {/* Overreliance warning banner */}
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
            You have submitted multiple convergent/decision-making prompts in the last 10 minutes (score: {summary.overreliance_score}). 
            HCI research indicates that offloading personal choices and analytical reasoning to automated systems risks automation bias—substituting active critical thinking for machine output. 
            Consider addressing these tasks directly using your own analytical judgment.
          </p>
        </section>
      )}

      {/* Error state */}
      {error && (
        <div className="error-banner" id="error-banner" aria-live="assertive">
          [ ERROR ]: {error}
        </div>
      )}

      {/* Prompt input form */}
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

      {/* Latest Result */}
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
        </section>
      )}

      {/* Session stats & visualization */}
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

          <div className="chart-container">
            <StatsChart history={history} />
          </div>
        </section>
      )}

      {/* History Feed */}
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
                className={`history-item ${item.classification}`}
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
    </div>
  );
};

export default App;

