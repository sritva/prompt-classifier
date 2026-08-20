# Prompt Classifier & Overreliance Monitor

A full-stack web application that classifies user-submitted prompts as **convergent** or **divergent** using OpenAI (with structured outputs) or a local heuristic fallback. The application tracks thinking profiles across a session and warns when a user shows signs of overreliance on AI for convergent decision-making tasks they could likely reason through themselves.

---

## 1. Theoretical Background & Citations

### Guilford's Structure of Intellect
The distinction between convergent and divergent thinking comes from J. P. Guilfordâ€™s landmark psychological research in the 1950s:
*   **Convergent Thinking**: Narrows down from multiple inputs towards a single correct, logical, or verifiable answer (e.g., mathematics, factual lookups, syntax debugging).
*   **Divergent Thinking**: Expands outwards, generating multiple valid possibilities, ideas, or creative alternatives (e.g., brainstorming, creative writing, drafting alternatives).

> **Citation**: Guilford, J. P. (1950). *Creativity*. American Psychologist, 5(9), 444â€“454.

### Cognitive Offloading & Automation Bias
Premise: Overreliance on AI presents different cognitive risks depending on the thinking task. 
*   For **divergent tasks** (brainstorming, drafting), AI acts as a creative sounding board, reducing initial ideation friction.
*   For **convergent tasks** (calculations, factual lookup), cognitive offloading is highly convenient but can make users susceptible to **Automation Bias**â€”the human tendency to accept computer-generated recommendations without verifying them or performing independent cognitive work.
*   The riskiest offloading involves **convergent-framed decisions** (e.g., "should I accept this job offer?"). Although users frame these as having a single "correct" answer, they are deeply subjective choices requiring personal judgment. Outsourcing this judgment to LLMs weakens human agency and critical reasoning.

> **Citation**: Parasuraman, R., & Manzey, D. H. (2010). *Complacency and Bias in Human Use of Automation*. Human Factors, 52(3), 381â€“410.

---

## 2. Overreliance Scoring Formula & Rationale

We track user prompts in a rolling **10-minute window**. The score is computed using the following weights:

*   `decision_making` (convergent): **+3 points** per prompt (highest risk; represents offloading critical personal agency).
*   `code_debugging` (convergent): **+2 points** per prompt (moderate risk; offloads code debugging which would otherwise train mental models).
*   `computation`, `factual_lookup`, `other` (convergent): **+1 point** each (low risk; basic offloading).
*   `divergent` prompts: **-1 point** each (mitigates the overreliance score, floor of 0; reflects balanced creative ideation).

### Thresholds
*   Score $\ge 8$: **High Overreliance** (Stark crimson warning banner triggered).
*   Score $\ge 5$: **Moderate Overreliance** (Crimson warning banner triggered).
*   Score $\ge 2$: **Low Overreliance** (Muted stats alert).
*   Score $< 2$: **None** (Neutral profile).

---

## 3. Tech Stack

*   **Backend**: Python 3.11+, FastAPI (sync router), SQLite via SQLAlchemy ORM, Alembic migrations.
*   **Frontend**: React, TypeScript, Vite, Recharts (visualizing thinking subtypes).
*   **Classification**: OpenAI GPT-4o-mini structured outputs (`response_format`) or regex/heuristic parser fallback.
*   **Testing**: `pytest` for backend, `vitest` + `react-testing-library` for frontend.

---

## 4. API Documentation

### 1. `POST /api/classify`
Submits a prompt for classification. Rate-limited using an in-memory token-bucket.
*   **Request Body**:
    ```json
    {
      "prompt": "Should I accept the job offer at Company A or B?",
      "session_id": "sess_xyz_12345"
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
      "reasoning": "Classified as decision-making since it involves evaluating personal life choices.",
      "created_at": "2026-08-14T12:00:00Z",
      "session_summary": {
        "total_prompts": 3,
        "convergent_percentage": 100.0,
        "divergent_percentage": 0.0,
        "overreliance_score": 6,
        "overreliance_signal": "moderate"
      }
    }
    ```

### 2. `GET /api/session/{session_id}`
Returns the full chronological history and active summary of a session.
*   **Response Body**:
    ```json
    {
      "session_id": "sess_xyz_12345",
      "history": [
        {
          "id": 12,
          "prompt": "Should I accept the job offer at Company A or B?",
          "classification": "convergent",
          "subtype": "decision_making",
          "confidence": 0.92,
          "reasoning": "Evaluating personal life choices.",
          "created_at": "2026-08-14T12:00:00Z"
        }
      ],
      "session_summary": { ... }
    }
    ```

### 3. `DELETE /api/session/{session_id}`
Clears session history from the database database.
*   **Response**:
    ```json
    { "message": "Session history cleared successfully" }
    ```

---

## 5. Setup & Installation Guide

### Prerequisites
*   Python 3.11+ installed.
*   Node.js v20+ installed.

### Backend Setup
1. Navigate to the backend folder:
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
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy configurations and create `.env` (optional):
   ```bash
   cp .env.example .env
   # Configure LLM_API_KEY and LLM_BASE_URL; otherwise, fallback heuristics run automatically
   ```
5. Apply database migrations using Alembic:
   ```bash
   alembic upgrade head
   ```
6. Start the FastAPI backend server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

### Frontend Setup
1. Open a new terminal session and navigate to the frontend folder:
   ```bash
   cd frontend
   ```
2. Install npm packages:
   ```bash
   npm install
   ```
3. Run the Vite development server:
   ```bash
   npm run dev
   ```
4. Open your browser to `http://localhost:5173`.

---

## 6. Running Tests

### Backend Tests (pytest)
```bash
cd backend
$env:PYTHONPATH="."  # Windows PowerShell
# OR (macOS/Linux): export PYTHONPATH="."
pytest
```

### Frontend Tests (vitest)
```bash
cd frontend
npm run test
```

---

## 7. Limitations

1.  **Error Rates**: LLM classifiers carry an inherent error rate and might miscategorize prompts based on subtle formatting details.
2.  **Fallback Weaknesses**: The local heuristic fallback uses keyword/regex matches. It is structurally weaker than the OpenAI model and can be fooled by prompts containing overlapping vocabulary (e.g. writing a "poem about code").
3.  **Non-Clinical Tool**: This application utilizes a simple point system to show patterns. It is an educational and reflective tool designed to prompt introspection about AI reliance, not a clinical or behavioral diagnostic instrument.

---