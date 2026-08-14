export interface PromptRecord {
  id?: number;
  prompt: string;
  classification: "convergent" | "divergent";
  subtype: "factual_lookup" | "computation" | "code_debugging" | "decision_making" | "other" | null;
  confidence: number;
  reasoning: string;
  created_at: string;
}

export interface SessionSummary {
  total_prompts: number;
  convergent_percentage: number;
  divergent_percentage: number;
  overreliance_score: number;
  overreliance_signal: "high" | "moderate" | "low" | "none";
}

export interface ClassifyResponse extends PromptRecord {
  session_summary: SessionSummary;
}

export interface SessionHistoryResponse {
  session_id: string;
  history: PromptRecord[];
  session_summary: SessionSummary;
}
