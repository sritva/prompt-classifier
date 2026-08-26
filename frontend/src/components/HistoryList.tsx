import React from "react";
import type { PromptRecord } from "../types";

interface HistoryListProps {
  history: PromptRecord[];
  selectedPromptId?: number;
  onSelectPrompt: (item: PromptRecord) => void;
  onClear: () => void;
}

export const HistoryList: React.FC<HistoryListProps> = ({
  history,
  selectedPromptId,
  onSelectPrompt,
  onClear,
}) => {
  if (history.length === 0) return null;

  return (
    <section className="history-section" id="history-section">
      <div className="history-header-row">
        <h2 className="history-title">session timeline</h2>
        <button onClick={onClear} className="clear-btn" id="clear-btn">
          Reset Session
        </button>
      </div>

      <div className="history-feed">
        {[...history].reverse().map((item, index) => (
          <div
            key={item.id || index}
            className={`history-item ${item.classification} ${selectedPromptId === item.id ? "selected" : ""}`}
            onClick={() => onSelectPrompt(item)}
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
  );
};
