import { useState, useEffect } from "react";
import {
  getOrCreateSessionId,
  resetSessionId,
  classifyPrompt,
  getSessionHistory,
  clearSessionHistory,
} from "../api";
import type { PromptRecord, SessionSummary } from "../types";

export function useSession() {
  const [sessionId, setSessionId] = useState<string>("");
  const [history, setHistory] = useState<PromptRecord[]>([]);
  const [summary, setSummary] = useState<SessionSummary | null>(null);
  const [latestResult, setLatestResult] = useState<PromptRecord | null>(null);
  const [selectedPrompt, setSelectedPrompt] = useState<PromptRecord | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [dismissedWarning, setDismissedWarning] = useState<boolean>(false);

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

  const submitPrompt = async (promptText: string) => {
    if (!promptText.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const result = await classifyPrompt(promptText, sessionId);
      setLatestResult(result);
      setHistory((prev) => [...prev, result]);
      setSummary(result.session_summary);
      if (result.session_summary.overreliance_signal !== "none") {
        setDismissedWarning(false);
      }
      return result;
    } catch (err: any) {
      setError(err.message || "An unexpected error occurred during classification.");
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const clearSession = async () => {
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

  return {
    sessionId,
    history,
    summary,
    latestResult,
    selectedPrompt,
    setSelectedPrompt,
    loading,
    error,
    setError,
    dismissedWarning,
    setDismissedWarning,
    submitPrompt,
    clearSession,
  };
}
