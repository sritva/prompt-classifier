import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach } from "vitest";
import App from "../src/App";
import * as api from "../src/api";
import { ClassifyResponse, SessionHistoryResponse } from "../src/types";

// Mock Recharts since JSDOM does not calculate container dimensions
vi.mock("recharts", () => {
  return {
    ResponsiveContainer: ({ children }: any) => <div data-testid="responsive-container">{children}</div>,
    BarChart: ({ children }: any) => <div data-testid="bar-chart">{children}</div>,
    Bar: () => <div />,
    XAxis: () => <div />,
    YAxis: () => <div />,
    Tooltip: () => <div />,
    Cell: () => <div />,
  };
});

describe("Prompt Classifier Frontend App", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    
    // Default mocks
    vi.spyOn(api, "getOrCreateSessionId").mockReturnValue("test-session-id");
    vi.spyOn(api, "getSessionHistory").mockResolvedValue({
      session_id: "test-session-id",
      history: [],
      session_summary: {
        total_prompts: 0,
        convergent_percentage: 0,
        divergent_percentage: 0,
        overreliance_score: 0,
        overreliance_signal: "none",
      },
    });
  });

  it("renders the empty state and title correctly", async () => {
    render(<App />);
    
    expect(screen.getByText("prompt classifier")).toBeInTheDocument();
    expect(screen.getByText("guilford cognitive tool")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Submit a prompt to analyze thinking style...")).toBeInTheDocument();
    
    // Ensure stats/history sections are not present initially
    expect(screen.queryByText("session profile")).not.toBeInTheDocument();
    expect(screen.queryByText("session timeline")).not.toBeInTheDocument();
  });

  it("displays loading state when analyzing a prompt", async () => {
    // Mock classify call with a delayed resolution
    const delayedResolve = new Promise<ClassifyResponse>((resolve) => {
      setTimeout(() => {
        resolve({
          prompt: "What is 2+2?",
          classification: "convergent",
          subtype: "computation",
          confidence: 0.95,
          reasoning: "Computation task.",
          created_at: new Date().toISOString(),
          session_summary: {
            total_prompts: 1,
            convergent_percentage: 100,
            divergent_percentage: 0,
            overreliance_score: 1,
            overreliance_signal: "none",
          },
        });
      }, 50);
    });

    vi.spyOn(api, "classifyPrompt").mockReturnValue(delayedResolve);

    render(<App />);

    const textarea = screen.getByPlaceholderText("Submit a prompt to analyze thinking style...");
    const submitBtn = screen.getByRole("button", { name: "Classify Prompt" });

    fireEvent.change(textarea, { target: { value: "What is 2+2?" } });
    fireEvent.click(submitBtn);

    // Assert loading text on button
    expect(screen.getByRole("button", { name: "Analyzing..." })).toBeInTheDocument();
    expect(textarea).toBeDisabled();

    // Wait for resolve
    await waitFor(() => {
      expect(screen.getByText("What is 2+2?")).toBeInTheDocument();
    });
  });

  it("renders success state and adds prompt to history", async () => {
    const mockResult: ClassifyResponse = {
      prompt: "Explain relativity.",
      classification: "convergent",
      subtype: "factual_lookup",
      confidence: 0.9,
      reasoning: "Requesting a physical theory explanation.",
      created_at: new Date().toISOString(),
      session_summary: {
        total_prompts: 1,
        convergent_percentage: 100,
        divergent_percentage: 0,
        overreliance_score: 1,
        overreliance_signal: "low",
      },
    };

    vi.spyOn(api, "classifyPrompt").mockResolvedValue(mockResult);

    render(<App />);

    const textarea = screen.getByPlaceholderText("Submit a prompt to analyze thinking style...");
    const submitBtn = screen.getByRole("button", { name: "Classify Prompt" });

    fireEvent.change(textarea, { target: { value: "Explain relativity." } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      // Latest result card displays reasoning
      expect(screen.getAllByText("Requesting a physical theory explanation.")[0]).toBeInTheDocument();
      // Badge details
      expect(screen.getByText("convergent (factual_lookup)")).toBeInTheDocument();

      // Summary profile shows up
      expect(screen.getByText("session profile")).toBeInTheDocument();
      expect(screen.getByText("total prompts")).toBeInTheDocument();
    });
  });

  it("handles error states (e.g. network failure / rate limit)", async () => {
    vi.spyOn(api, "classifyPrompt").mockRejectedValue(new Error("Rate limit exceeded. Try again in a few seconds."));

    render(<App />);

    const textarea = screen.getByPlaceholderText("Submit a prompt to analyze thinking style...");
    const submitBtn = screen.getByRole("button", { name: "Classify Prompt" });

    fireEvent.change(textarea, { target: { value: "Tell me a joke" } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText("[ ERROR ]: Rate limit exceeded. Try again in a few seconds.")).toBeInTheDocument();
    });
  });

  it("shows the overreliance banner when signal is high and allows dismissal", async () => {
    // Mock history to trigger overreliance
    vi.spyOn(api, "getSessionHistory").mockResolvedValue({
      session_id: "test-session-id",
      history: [
        {
          prompt: "Decision 1",
          classification: "convergent",
          subtype: "decision_making",
          confidence: 0.9,
          reasoning: "Evaluating choices.",
          created_at: new Date().toISOString(),
        },
        {
          prompt: "Decision 2",
          classification: "convergent",
          subtype: "decision_making",
          confidence: 0.9,
          reasoning: "Evaluating choices.",
          created_at: new Date().toISOString(),
        },
        {
          prompt: "Decision 3",
          classification: "convergent",
          subtype: "decision_making",
          confidence: 0.9,
          reasoning: "Evaluating choices.",
          created_at: new Date().toISOString(),
        },
      ],
      session_summary: {
        total_prompts: 3,
        convergent_percentage: 100,
        divergent_percentage: 0,
        overreliance_score: 9,
        overreliance_signal: "high",
      },
    });

    render(<App />);

    // Wait for render
    await waitFor(() => {
      expect(screen.getByText(/WARNING: COGNITIVE OVERRELIANCE/i)).toBeInTheDocument();
      expect(screen.getByText(/risks automation bias/i)).toBeInTheDocument();
    });

    // Dismiss banner
    const dismissBtn = screen.getByRole("button", { name: "Dismiss overreliance warning" });
    fireEvent.click(dismissBtn);

    // Verify dismissed
    expect(screen.queryByText(/WARNING: COGNITIVE OVERRELIANCE/i)).not.toBeInTheDocument();
  });
});
