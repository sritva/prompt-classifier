import React from "react";
import type { PromptRecord } from "../types";

interface CognitiveDetailModalProps {
  selectedPrompt: PromptRecord | null;
  onClose: () => void;
}

export const CognitiveDetailModal: React.FC<CognitiveDetailModalProps> = ({
  selectedPrompt,
  onClose,
}) => {
  if (!selectedPrompt) return null;

  return (
    <section className="details-card" id="selected-details">
      <div className="details-header-row">
        <h2 className="details-title">selected prompt analysis</h2>
        <button onClick={onClose} className="close-details-btn">
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
  );
};
