import React, { useState } from "react";

interface PromptInputFormProps {
  onSubmit: (prompt: string) => Promise<void>;
  loading: boolean;
}

export const PromptInputForm: React.FC<PromptInputFormProps> = ({ onSubmit, loading }) => {
  const [prompt, setPrompt] = useState<string>("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || loading) return;
    try {
      await onSubmit(prompt);
      setPrompt("");
    } catch {
      // Error handled by useSession
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <main>
      <form onSubmit={handleSubmit} className="prompt-form" id="prompt-form">
        <div className="input-wrapper">
          <textarea
            className="prompt-textarea"
            id="prompt-textarea"
            placeholder="Submit a prompt to analyze thinking style..."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={handleKeyDown}
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
  );
};
