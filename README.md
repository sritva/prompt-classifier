# Prompt Classifier & Overreliance Monitor

A full-stack web application that classifies user-submitted prompts as **convergent** or **divergent** using an LLM via any OpenAI-API-compatible provider (configured for OpenRouter by default, with structured outputs) or a local heuristic fallback. The application tracks thinking profiles across a session and warns when a user shows signs of overreliance on AI for convergent decision-making tasks they could likely reason through themselves.

---

## 1. Theoretical Background & Citations

### Guilford's Structure of Intellect
The distinction between convergent and divergent thinking comes from J. P. Guilford’s landmark psychological research in the 1950s:
*   **Convergent Thinking**: Narrows down from multiple inputs towards a single correct, logical, or verifiable answer (e.g., mathematics, factual lookups, syntax debugging).
*   **Divergent Thinking**: Expands outwards, generating multiple valid possibilities, ideas, or creative alternatives (e.g., brainstorming, creative writing, drafting alternatives).

> **Citation**: Guilford, J. P. (1950). *Creativity*. American Psychologist, 5(9), 444–454.

### Cognitive Offloading & Automation Bias
Premise: Overreliance on AI presents different cognitive risks depending on the thinking task. 
*   For **divergent tasks** (brainstorming, drafting), AI acts as a creative sounding board, reducing initial ideation friction.
*   For **convergent tasks** (calculations, factual lookup), cognitive offloading is highly convenient but can make users susceptible to **Automation Bias**—the human tendency to accept computer-generated recommendations without verifying them or performing independent cognitive work.
*   The riskiest offloading involves **convergent-framed decisions** (e.g., "should I accept this job offer?"). Although users frame these as having a single "correct" answer, they are deeply subjective choices requiring personal judgment. Outsourcing this judgment to LLMs weakens human agency and critical reasoning.

> **Citation**: Parasuraman, R., & Manzey, D. H. (2010). *Complacency and Bias in Human Use of Automation*. Human Factors, 52(3), 381–410.

---

## 2. Overreliance Scoring Formula & Rationale

We track user prompts in a rolling **10-minute window**. The score is computed using the following weights:

*   `decision_making` (convergent): **+3 points** per prompt (highest risk; represents offloading critical personal agency).
*   `code_debugging` (convergent): **+2 points** per prompt (moderate risk; offloads code debugging which would otherwise train mental models).
*   `computation`, `factual_lookup`, `other` (convergent): **+1 point** each (low risk; basic offloading).
*   `divergent` prompts: **-1 point** each (mitigates the overreliance score, floor of 0; reflects balanced creative ideation).

### Thresholds & Behavioral Interventions
*   **Score $\ge 8$ — High Overreliance**: Stark crimson banner with high-priority warnings, behavioral reflection nudges, and suggested alternatives.
*   **Score $\ge 5$ — Moderate Overreliance**: Warning banner with recommendations to pause and engage in independent synthesis.
*   **Score $\ge 2$ — Low Overreliance**: Muted informational alert highlighting rising convergent tendency.
*   **Score $< 2$ — None**: Neutral profile indicating balanced usage.

---

## 3. Architecture & Tech Stack

### Backend Architecture
*   **FastAPI (Async Endpoints)**: Non-blocking asynchronous handlers for classification and session endpoints.
*   **LLM Integration & Connection Pooling**: Uses `AsyncOpenAI` with a single reused client instance across requests to maximize connection reuse and lower latency.
*   **Database & Session Management**: SQLite/PostgreSQL through SQLAlchemy ORM using `get_db` context-managed dependency injection. Schema migrations versioned via **Alembic** (with idempotent classifier version column migrations).
*   **Session Security**: Cryptographically signed session IDs (`secrets.token_urlsafe` + HMAC-SHA256) prevent session identifier tampering or unauthorized session enumeration.
*   **Bounded Rate Limiter**: IP-based in-memory token bucket (10 token burst capacity, 0.5 tokens/sec refill) equipped with 10-minute TTL bucket cleanup and an upper capacity bound (10,000 buckets) to prevent unbounded memory growth.
*   **Multi-Tier Caching & Low-Confidence Fallback**: True LRU in-memory cache using `collections.OrderedDict` with move-to-end eviction, TTL invalidation, and versioned keys (`v2.0.0`). LLM responses below a 0.6 confidence threshold automatically fallback to the local heuristic classifier, returning an explicit `is_heuristic` flag.

### Frontend Architecture
*   **React 19 + TypeScript + Vite**: Fast, typed single-page application.
*   **Component Decomposition**: Clean modular hierarchy:
    *   `Header`: Session status and branding.
    *   `SessionStats`: Live metrics (total prompts, convergent/divergent percentages, overreliance score).
    *   `PromptForm`: Text area with keyboard shortcuts (`Cmd/Ctrl + Enter`), loading indicators, and error banners.
    *   `OverrelianceBanner`: Progressive severity warnings and behavioral reflection nudges.
    *   `ThinkingDistributionChart`: Recharts-powered interactive breakdown of subtypes.
    *   `HistoryList`: Chronological prompt feed with expandable reasoning, confidence pills, and reflection prompts.
*   **Custom Session Hook (`useSession`)**: Handles cryptographic session initialization, localStorage persistence, optimistic updates, and automatic recovery.
*   **Vite Reverse Proxy**: Configured in `vite.config.ts` to proxy `/api` requests directly to `http://127.0.0.1:8000` for consistent local and production relative paths.

---

## 4. API Documentation

### 1. `POST /api/session`
Generates and returns a new cryptographically signed session ID.
*   **Response**:
    ```json
    {
      "session_id": "aBcD1234_xyz.7f83b1657ff1..."
    }
    ```

### 2. `POST /api/classify`
Submits a prompt for classification under the given signed session. Rate-limited using a bounded token bucket.
*   **Request Body**:
    ```json
    {
      "prompt": "Should I accept the job offer at Company A or B?",
      "session_id": "aBcD1234_xyz.7f83b1657ff1..."
    }
    ```
*   **Response Body**:
    ```json
    {
      "id": 12,
      "prompt": "Should I accept the job offer at Company A or B?",
      "classification": "convergent",
      "subtype": "decision_making",
      "confidence": 0.92,
      "reasoning": "Classified as decision-making since it involves evaluating personal career tradeoffs.",
      "created_at": "2026-08-14T12:00:00Z",
      "latency_ms": 120,
      "total_tokens": 340,
      "explanation_details": {
        "primary_cues": ["should I accept", "job offer"],
        "reasoning_steps": ["Detects personal judgment query with trade-off evaluation"]
      },
      "reflection_prompt": "Before deciding, what are the non-negotiable criteria you value most?",
      "is_heuristic": false,
      "session_summary": {
        "total_prompts": 3,
        "convergent_percentage": 100.0,
        "divergent_percentage": 0.0,
        "overreliance_score": 6,
        "overreliance_signal": "moderate"
      }
    }
    ```

### 3. `GET /api/session/{session_id}`
Returns the complete chronological prompt history and rolling 10-minute session summary.
*   **Response Body**:
    ```json
    {
      "session_id": "aBcD1234_xyz.7f83b1657ff1...",
      "history": [
        {
          "id": 12,
          "prompt": "Should I accept the job offer at Company A or B?",
          "classification": "convergent",
          "subtype": "decision_making",
          "confidence": 0.92,
          "reasoning": "Evaluating personal career tradeoffs.",
          "created_at": "2026-08-14T12:00:00Z",
          "latency_ms": 120,
          "total_tokens": 340,
          "reflection_prompt": "Before deciding, what are the non-negotiable criteria you value most?"
        }
      ],
      "session_summary": {
        "total_prompts": 1,
        "convergent_percentage": 100.0,
        "divergent_percentage": 0.0,
        "overreliance_score": 3,
        "overreliance_signal": "low"
      }
    }
    ```

### 4. `DELETE /api/session/{session_id}`
Clears session history from the database and resets the rolling window score.
*   **Response**:
    ```json
    {
      "message": "Session history cleared successfully"
    }
    ```

---

## 5. Setup & Installation Guide

### Prerequisites
*   Python 3.11+ installed.
*   Node.js v20+ installed.

### Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```
3. Install backend dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment variables (`.env`):
   ```bash
   cp .env.example .env
   # Edit .env to supply LLM_API_KEY, LLM_BASE_URL, and SESSION_SECRET_KEY
   ```
5. Apply database migrations using Alembic:
   ```bash
   alembic upgrade head
   ```
6. Run the FastAPI development server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

### Frontend Setup
1. In a separate terminal, navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install npm dependencies:
   ```bash
   npm install
   ```
3. Run the Vite development server:
   ```bash
   npm run dev
   ```
4. Access the web interface at `http://localhost:5173`.

---

## 6. Testing & Evaluation Suite

### Backend Test Suite (pytest)
Runs 57 unit and integration tests covering heuristic and LLM classification, session lifecycle, cryptographic signing, rate limiting, and cache invalidation:
```bash
cd backend
pytest
```

### Frontend Test Suite (Vitest)
Runs UI integration and unit tests using React Testing Library and thread-pool execution:
```bash
cd frontend
npm run test
```

### Frontend Lint & Build
```bash
cd frontend
npm run lint     # oxlint
npm run build    # tsc -b && vite build
```

### Quantitative Evaluation Benchmark
The project includes a benchmark suite in `backend/evaluation/` with release targets configured in `targets.json`:
*   `test_holdout.jsonl`: Independent test split for classification and subtype accuracy.
*   `adversarial.jsonl`: Tricky prompts with overlapping vocabulary (e.g. creative poems about debugging).
*   `session_traces.jsonl`: Multi-turn chronological session traces verifying overreliance alert precision and false warning rates.

Run the evaluation suite:
```bash
cd backend
# Evaluate holdout set with target gates
python evaluation/evaluate.py --dataset test_holdout.jsonl --check-targets

# Evaluate adversarial set
python evaluation/evaluate.py --dataset adversarial.jsonl --check-targets

# Run multi-threaded LLM evaluation (requires API key)
python evaluation/evaluate.py --mode llm --dataset test_holdout.jsonl --concurrency 4
```

---

## 7. Limitations & Disclaimers

1.  **Model Inherent Variance**: LLM classifiers carry an inherent error rate and can occasionally miscategorize subtle or ambiguous prompts.
2.  **Fallback Heuristic Boundary**: The local heuristic classifier relies on multi-cue weighted keyword scoring. While performing with 100% precision on holdout and adversarial benchmarks, complex natural language nuance may require the LLM classifier for optimal separation.
3.  **Educational and Reflective Purpose**: This application provides a quantitative reflection framework to raise self-awareness regarding AI dependency. It is not a clinical or psychological diagnostic tool.
4.  **Persistent Cache Invalidation**: Cached prompt classifications persist in-memory according to LRU and TTL limits. Changes to model definitions or classifier versions trigger automated version-keyed invalidation (`v2.0.0`).
