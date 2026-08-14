import type { ClassifyResponse, SessionHistoryResponse } from "./types";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function getOrCreateSessionId(): string {
  let id = localStorage.getItem("prompt_classifier_session_id");
  if (!id) {
    id = "sess_" + Math.random().toString(36).substring(2, 11) + "_" + Date.now();
    localStorage.setItem("prompt_classifier_session_id", id);
  }
  return id;
}

export function resetSessionId(): string {
  const id = "sess_" + Math.random().toString(36).substring(2, 11) + "_" + Date.now();
  localStorage.setItem("prompt_classifier_session_id", id);
  return id;
}

export async function classifyPrompt(prompt: string, sessionId: string): Promise<ClassifyResponse> {
  const response = await fetch(`${API_BASE}/api/classify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, session_id: sessionId }),
  });
  
  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    throw new Error(errData.detail || `Server error: ${response.status}`);
  }
  return response.json();
}

export async function getSessionHistory(sessionId: string): Promise<SessionHistoryResponse> {
  const response = await fetch(`${API_BASE}/api/session/${sessionId}`);
  if (!response.ok) {
    throw new Error(`Failed to load history: ${response.status}`);
  }
  return response.json();
}

export async function clearSessionHistory(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/session/${sessionId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(`Failed to clear session: ${response.status}`);
  }
}
