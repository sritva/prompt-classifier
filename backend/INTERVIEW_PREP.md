# Interview Preparation Study Guide: Prompt Classifier & Overreliance Monitor

This document provides an end-to-end, code-grounded technical review of the Prompt Classifier codebase, designed to serve as a comprehensive guide for walkthroughs, system design, and technical interviews.

---

## Table of Contents
- [1. The 30-Second Pitch](#1-the-30-second-pitch)
- [2. Terms & Technologies Glossary](#2-terms--technologies-glossary)
- [3. Architecture Walkthrough](#3-architecture-walkthrough)
- [4. The Classification System](#4-the-classification-system)
- [5. Reliability & Performance Features](#5-reliability--performance-features)
- [6. The Evaluation Methodology](#6-the-evaluation-methodology)
- [7. Known Limitations](#7-known-limitations)
- [8. Security History](#8-security-history)
- [9. The Provider-Agnostic Rename & Environment Harmonization](#9-the-provider-agnostic-rename--environment-harmonization)
- [10. Git History & Engineering Process](#10-git-history--engineering-process)
- [11. Anticipated Interview Questions & Model Answers](#11-anticipated-interview-questions--model-answers)
- [12. Weak Spots to Rehearse](#12-weak-spots-to-rehearse)

---

## 1. The 30-Second Pitch

"This project is a full-stack developer tooling application that classifies user-submitted prompts into **convergent** (single correct answer, like debugging or math) or **divergent** (creative, open-ended ideation) thinking categories based on J.P. Guilford’s Structure of Intellect. 

Its primary purpose is to monitor and calculate a session-based **overreliance score** in a rolling 10-minute window. If a user offloads too many subjective, convergent decisions (e.g., *'should I accept this job offer?'*) to the AI—which risks automation bias and compliance complacency—the app flags it with a warning banner and inserts a tailored 'reflective friction' prompt to encourage critical thinking. The system uses a fast, dual-layer caching system (in-memory LRU + persistent SQLite), is fully provider-agnostic, and has a dedicated offline evaluation harness to measure fallback performance."

---

## 2. Terms & Technologies Glossary

### Backend

*   **FastAPI**: A high-performance web framework for building APIs in Python using standard type hints. It supports native asynchronous handlers (`async/await`) and automatically generates interactive OpenAPI documentation.
    *   *Where it's used in this project*: Router endpoint configurations in [`backend/app/main.py`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/app/main.py).
*   **Pydantic (response_format / structured outputs)**: A data validation and parsing library that enforces strict type annotations at runtime. In this project, it defines the structured schema for model outputs, ensuring LLMs return strictly conforming JSON payloads.
    *   *Where it's used in this project*: Schemas like `PromptClassificationResult` in [`backend/app/classifier.py`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/app/classifier.py).
*   **SQLAlchemy ORM**: An Object-Relational Mapper that maps Python classes to database tables. It allows developers to define models, constraints, and relationships in Python code instead of raw SQL DDL.
    *   *Where it's used in this project*: Database schema models in [`backend/app/models.py`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/app/models.py).
*   **Alembic migrations**: A database migration tool for SQLAlchemy that records table additions and updates in versioned Python scripts. It allows developers to migrate databases up and down deterministically, maintaining database consistency across environments.
    *   *Where it's used in this project*: Migration files inside the [`backend/migrations/versions/`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/migrations/versions/) folder.
*   **SQLite**: A lightweight, serverless, file-based SQL database engine. It does not require a background daemon, instead reading and writing directly to a local file, making it ideal for self-contained desktop configurations.
    *   *Where it's used in this project*: Persistent SQLite database `prompt_classifier.db` initialized and queried in [`backend/app/session_store.py`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/app/session_store.py).
*   **uvicorn**: A high-speed ASGI server implementation for Python. It processes HTTP connections and forwards requests to ASGI frameworks like FastAPI.
    *   *Where it's used in this project*: Configured as the server entry point runner in `README.md` (`uvicorn app.main:app`).
*   **pytest + unittest.mock (MagicMock/patch)**: Pytest is the standard Python test runner. Unittest.mock provides mocking interfaces to replace network-dependent integrations (such as the OpenAI SDK) with predictable, mock responses during test verification.
    *   *Where it's used in this project*: Unit testing mocks in [`backend/tests/test_backend.py`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/tests/test_backend.py).

### Frontend

*   **React**: A popular, component-based frontend library that manages visual states and reactive DOM re-rendering using a Virtual DOM diffing engine.
    *   *Where it's used in this project*: Interface and layout composition in [`frontend/src/App.tsx`](file:///c:/Users/sriva/Desktop/prompt-classifier/frontend/src/App.tsx).
*   **TypeScript**: A typed superset of JavaScript that compiles to plain JavaScript. It adds build-time type checking to prevent null pointer references and mismatch errors between backend API interfaces and client components.
    *   *Where it's used in this project*: Frontend model contracts defined in [`frontend/src/types.ts`](file:///c:/Users/sriva/Desktop/prompt-classifier/frontend/src/types.ts).
*   **Vite**: A fast frontend tooling framework utilizing native ES modules for immediate local server hot-reloads and Rollup for optimized production builds.
    *   *Where it's used in this project*: Bundler configuration in [`frontend/vite.config.ts`](file:///c:/Users/sriva/Desktop/prompt-classifier/frontend/vite.config.ts).
*   **Recharts**: A declarative, React-specific charting library based on SVG components. It renders clean data visualizations directly from structured JSON datasets.
    *   *Where it's used in this project*: Interactive AreaChart and BarChart timelines in [`frontend/src/App.tsx`](file:///c:/Users/sriva/Desktop/prompt-classifier/frontend/src/App.tsx).
*   **vitest + react-testing-library**: Vitest is a fast unit-testing framework integrated with Vite, while react-testing-library renders React components to verify that user interactions (clicks, text input) produce correct DOM updates.
    *   *Where it's used in this project*: Frontend rendering test checks in [`frontend/src/App.test.tsx`](file:///c:/Users/sriva/Desktop/prompt-classifier/frontend/src/App.test.tsx).

### AI/LLM Concepts

*   **LLM (Large Language Model)**: A deep learning model trained on large text datasets to predict next-token distributions, allowing it to perform natural language parsing, generation, and classification.
    *   *Where it's used in this project*: Evaluates prompt classification categories inside [`backend/app/classifier.py`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/app/classifier.py).
*   **OpenAI Python SDK**: The official Python library to interface with OpenAI's API. Because it accepts custom API keys and base URLs, it is commonly used as a universal interface for other OpenAI-compatible endpoints.
    *   *Where it's used in this project*: SDK instance creation in [`backend/app/classifier.py`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/app/classifier.py).
*   **OpenRouter**: A unified API aggregator that serves as a router. It accepts OpenAI-standard requests and proxies them to hundreds of open-source or proprietary models hosted across different providers.
    *   *Where it's used in this project*: The default value for `LLM_BASE_URL` in [`.env.example`](file:///c:/Users/sriva/Desktop/prompt-classifier/.env.example).
*   **Structured Outputs / JSON Mode**: API configuration formats forcing the LLM to output valid JSON. Structured outputs (e.g. OpenAI's `.parse()`) compile Pydantic models directly into JSON schemas to guarantee structural conformance, while JSON mode only guarantees that output strings are syntactically valid JSON.
    *   *Where it's used in this project*: Configured dynamically based on provider in [`backend/app/classifier.py`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/app/classifier.py).
*   **Prompt Classification**: The machine learning task of assigning semantic categories to user prompts. In this codebase, it divides prompts into convergent (factual/logical resolution) and divergent (ideation) thinking categories.
    *   *Where it's used in this project*: Routing logic inside the `classify_prompt` function in [`backend/app/classifier.py`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/app/classifier.py).
*   **Confidence Score**: A probability score (usually between 0.0 and 1.0) indicating how certain the model is about its classification choice.
    *   *Where it's used in this project*: Verified against `CONFIDENCE_THRESHOLD = 0.6` in `classify_prompt` in [`backend/app/classifier.py`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/app/classifier.py).
*   **Zero-Shot Classification**: A method of categorizing text without training the model on labeled data. The model instead relies solely on pre-existing semantic associations and instructions provided in the system prompt.
    *   *Where it's used in this project*: Prompt classification system prompt definitions in [`backend/app/classifier.py`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/app/classifier.py).
*   **Regex/Heuristic Classification**: A deterministic, rule-based text classification approach using regular expressions to match pre-defined keywords. It provides a zero-cost fallback when API keys are absent or network requests fail.
    *   *Where it's used in this project*: The `classify_heuristically` fallback function in [`backend/app/classifier.py`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/app/classifier.py).

### Software Engineering Practices

*   **CI/CD**: Continuous Integration / Continuous Deployment. An automated pipeline that builds code, runs tests, and checks for security vulnerabilities on every push or pull request to verify that updates do not break the system.
    *   *Where it's used in this project*: Workflow configurations in [`.github/workflows/ci.yml`](file:///c:/Users/sriva/Desktop/prompt-classifier/.github/workflows/ci.yml).
*   **Gitleaks / Secret Scanning**: A security scanner that inspects git history for high-entropy strings and credentials (such as API keys), preventing developers from pushing secrets to public repositories.
    *   *Where it's used in this project*: The `Secret Scan` build step in [`.github/workflows/ci.yml`](file:///c:/Users/sriva/Desktop/prompt-classifier/.github/workflows/ci.yml).
*   **LRU Cache**: Least Recently Used cache. A memory-bounded caching mechanism that discards the oldest unmodified keys when cache capacity is exceeded to prevent out-of-memory crashes.
    *   *Where it's used in this project*: In-memory cache dictionary `CLASSIFIER_CACHE` in [`backend/app/classifier.py`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/app/classifier.py).
*   **Rate Limiting / Token-Bucket**: A traffic control algorithm where requests consume tokens from a bucket. The bucket refills at a fixed rate, blocking or delaying incoming requests if it is empty to prevent API overload.
    *   *Where it's used in this project*: API route rate-limiting middleware in [`backend/app/main.py`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/app/main.py).
*   **Database Migrations vs. Auto-DDL**: Migrations are version-controlled, incremental SQL scripts that update schema states step-by-step. Auto-DDL dynamically alters database schemas on server start, which risks data corruption and breaks environment staging parity.
    *   *Where it's used in this project*: Versioned migrations under [`backend/migrations/versions/`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/migrations/versions/).
*   **Git Commit Granularity / Atomic Commits**: The practice of splitting code updates into small, single-purpose commits. This ensures that every commit focuses on a single logical change, making debugging, code reviews, and rollbacks straightforward.
    *   *Where it's used in this project*: Granular commits separating layout redesigns, caching layers, and provider-agnostic changes in `git log`.

### Evaluation & ML Concepts

*   **Precision**: The percentage of positive predictions that are truly positive. *"Out of all prompts our fallback classified as factual lookups, how many were actually factual lookups?"*
    *   *Where it's used in this project*: Factual subtype precision calculation in [`backend/evaluation/results.json`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/evaluation/results.json).
*   **Recall**: The percentage of actual positives that were correctly identified. *"Out of all actual factual lookup prompts in our dataset, how many did the fallback classifier successfully catch?"*
    *   *Where it's used in this project*: Factual subtype recall calculation in [`backend/evaluation/results.json`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/evaluation/results.json).
*   **F1 Score**: The harmonic mean of precision and recall. It balances false positives and false negatives, providing a single metric to evaluate classification performance on imbalanced datasets.
    *   *Where it's used in this project*: Factual subtype F1 score calculation in [`backend/evaluation/results.json`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/evaluation/results.json).
*   **Confusion Matrix**: A table layout displaying actual class labels versus model predicted labels, highlighting exactly which categories are misclassified.
    *   *Where it's used in this project*: Classification and subtype matrices in [`backend/evaluation/results.json`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/evaluation/results.json).
*   **Train/Test Split**: The process of dividing a dataset into a training subset (used to tune model parameters or regex keywords) and a testing subset (used to evaluate performance on unseen data).
    *   *Where it's used in this project*: Labeled datasets stored under [`backend/evaluation/`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/evaluation/).
*   **Holdout Set**: A final validation dataset kept completely separate from training and tuning phases. In this project, it was built *after* the heuristic was tuned to evaluate its generalizability. This prevented developers from adjusting regexes to fit the holdout queries, revealing that the heuristic fallback overfit to the training set's phrasing.
    *   *Where it's used in this project*: Test metrics generated using [`backend/evaluation/dataset_holdout.jsonl`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/evaluation/dataset_holdout.jsonl).
*   **Overfitting**: A modeling error occurring when a system matches training data too closely, capturing noise or specific patterns instead of general rules, which degrades accuracy on unseen test data.
    *   *Where it's used in this project*: Revealed by the factual lookup recall dropping to 52% on the holdout set, analyzed in `README.md`.
*   **Support**: The absolute count of true occurrences of a class or label within a given dataset split.
    *   *Where it's used in this project*: Support metrics under `subtype` in [`backend/evaluation/results.json`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/evaluation/results.json).

### Domain-Specific Concepts

*   **Convergent Thinking**: A cognitive process focused on compiling logical facts to arrive at a single, correct, or verifiable solution to a problem.
    *   *Where it's used in this project*: Core category classifications like `factual_lookup` and `computation` in [`backend/app/classifier.py`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/app/classifier.py).
*   **Divergent Thinking**: A cognitive process focused on open-ended ideation to generate multiple creative alternatives or possibilities.
    *   *Where it's used in this project*: Creative category classifications like `originality` and `flexibility` in [`backend/app/classifier.py`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/app/classifier.py).
*   **Guilford's Structure of Intellect**: J.P. Guilford's 1950s intelligence model separating human reasoning into multiple dimensions, providing the theoretical foundation for separating convergent and divergent thinking.
    *   *Where it's used in this project*: The theoretical background documented in section 1 of `README.md`.
*   **Automation Bias**: The human tendency to trust automated decision-making recommendations blindly, ignoring conflicting information or failing to verify results.
    *   *Where it's used in this project*: The behavioral rationale for warnings in [`frontend/src/App.tsx`](file:///c:/Users/sriva/Desktop/prompt-classifier/frontend/src/App.tsx).
*   **Cognitive Offloading**: The practice of using external tools (like calculators, search engines, or LLMs) to reduce mental workload, which can lead to cognitive atrophy if overused for critical decision-making.
    *   *Where it's used in this project*: The behavioral rationale for tracking overreliance on AI in [`frontend/src/App.tsx`](file:///c:/Users/sriva/Desktop/prompt-classifier/frontend/src/App.tsx).

---

## 3. Architecture Walkthrough

### Request Lifecycle for `POST /api/classify`

The following diagram outlines the path a single user prompt takes from the frontend client to the database and back:

```text
[Frontend Client]
       │
       ▼ (HTTP POST /api/classify)
[FastAPI Router (main.py)] ────► [Pydantic Request Validation (ClassifyRequest)]
       │
       ▼
[Classifier (classifier.py)] ──► [In-Memory LRU Cache Check (CLASSIFIER_CACHE)] ──(Hit)──► [Return Result]
       │ (Miss)
       ▼
[Persistent DB Cache Check] ──► [Query SQLite Table (prompt_records)] ───────────(Hit)──► [Cache In-Memory & Return]
       │ (Miss)
       ▼
[API Key Validation] ────────► [No Key / Placeholder] ───────────────────────────(True)─► [Local Heuristic Fallback]
       │ (Valid Key)                                                                                 │
       ▼                                                                                             │
[OpenAI SDK Client]                                                                                  │
       │                                                                                             │
       ├─► [Structured Output (parse)] ──► (Low Confidence < 0.6) ───────────────────────────────────┤
       │                                                                                             │
       ├─► [JSON Mode Fallback (create)]                                                             │
       ▼                                                                                             │
[Format API Result] ◄────────────────────────────────────────────────────────────────────────────────┘
       │
       ▼ (Calculate Overreliance Score & Signal)
[session_store.add_prompt_record] ──► [Write to SQLite DB]
       │
       ▼ (HTTP 200 OK)
[Frontend Client (Redraw Dashboard & Recharts Graphs)]
```

### Request Lifecycle Phases in the Code
1.  **Routing & Validation**: The frontend POSTs `{"prompt": "...", "session_id": "..."}` to `/api/classify` in [`backend/app/main.py`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/app/main.py). FastAPI validates it using the `ClassifyRequest` Pydantic schema.
2.  **In-Memory Cache Check**: In `classify_prompt()` inside [`backend/app/classifier.py`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/app/classifier.py), the prompt is stripped, normalized to lowercase, and hashed (SHA-256). The hash is checked against the session-scoped dict `CLASSIFIER_CACHE`.
3.  **Persistent DB Cache Check**: On an in-memory miss, `session_store.get_cached_prompt_record(prompt)` in [`backend/app/session_store.py`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/app/session_store.py) runs a case-insensitive, trimmed lookup on the `prompt_records` SQLite table. If found, it populates `CLASSIFIER_CACHE` and returns it.
4.  **LLM Call Path**: If a cache miss occurs, the system inspects `LLM_API_KEY`. If empty or containing `"placeholder"`, it immediately invokes `classify_heuristically()`. If valid, it instantiates `OpenAI(api_key, base_url)` pointing to `LLM_BASE_URL` (defaulting to OpenRouter).
5.  **Structured Output & Fallback Parsing**:
    *   **OpenAI official path**: Calls `client.beta.chat.completions.parse` utilizing the `PromptClassificationResult` response format.
    *   **Compatible custom provider path (OpenRouter/Ollama)**: Calls `client.chat.completions.create` with JSON mode enabled and parses the string response using `json.loads`.
6.  **Confidence Check**: If `parsed.confidence < 0.6`, it discards the LLM classification, runs the local fallback, and appends `"(LLM confidence below threshold, using heuristic fallback)"` to the `reasoning` field.
7.  **Write & Score**: The FastAPI handler writes the result (including timed `latency_ms` and `total_tokens`) to the SQLite database via `session_store.add_prompt_record()`, recalculates the rolling 10-minute overreliance score, and returns the unified `ClassifyResponse` to the client.

### Tech Stack Decisions & Rationales
*   **FastAPI**: Chosen for its high concurrency support via Python's `async/await` syntax and native integration with Pydantic for request/response serialization and schema enforcement.
*   **SQLAlchemy + Alembic**: SQLAlchemy provides a Pythonic ORM abstraction layer to handle SQL operations cleanly. Alembic allows version-controlled, linear migrations (essential for transitioning from basic schemas to tracking caching/reflection columns).
*   **React + TypeScript + Vite**: React provides responsive rendering of the UI. TypeScript guarantees type safety between backend models and frontend components. Vite offers fast Hot Module Replacement (HMR) for development.
*   **OpenRouter via OpenAI SDK**: The OpenAI SDK is the industry-standard client. Because it supports a configurable `base_url`, we can easily swap standard OpenAI endpoints for OpenRouter, allowing us to route requests to free, open-weights models like `nvidia/nemotron-3-super-120b-a12b:free` without changing SDK logic.

---

## 4. The Classification System

### Guilford Theory and Rationale
*   **Convergent Thinking**: Narrows down from multiple inputs towards a single correct, logical, or verifiable answer (Guilford 1950). In our code, these are categorized into 5 subtypes: `factual_lookup`, `computation`, `code_debugging`, `decision_making`, and `other`.
*   **Divergent Thinking**: Expands outwards, generating multiple valid possibilities, ideas, or creative alternatives. In our code, these map to Guilford's 4 creative domains: `fluency`, `flexibility`, `originality`, and `elaboration`.
*   **Cognitive Offloading (Parasuraman & Manzey 2010)**: Offloading convergent choices (especially `decision_making` like life/job choices) bypasses critical human reasoning and induces automation bias, where users blindly trust machine output. The weighting formula (+3 decision, +2 code, +1 factual/comp/other, -1 divergent) actively measures this cognitive risk.

### Structured Output Architecture
The Pydantic models in [`backend/app/classifier.py`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/app/classifier.py) define the API contract with the LLM:

```python
class StructuredExplanation(BaseModel):
    given_inputs: list[str]
    expected_outputs: list[str]
    creative_freedom_score: float
    factual_dependency: Literal["low", "medium", "high"]
    complexity: Literal["low", "medium", "high"]

class PromptClassificationResult(BaseModel):
    classification: Literal["convergent", "divergent"]
    confidence: float
    reasoning: str
    subtype: Optional[Literal["factual_lookup", "computation", "code_debugging", "decision_making", "other", "fluency", "flexibility", "originality", "elaboration"]] = None
    explanation_details: Optional[StructuredExplanation] = None
    reflection_prompt: Optional[str] = None
```

To support non-OpenAI endpoints (like OpenRouter) which do not support the newer `.parse()` SDK endpoint, the code falls back gracefully:
```python
is_openai_official = not base_url or "api.openai.com" in base_url
if is_openai_official and model.startswith("gpt-"):
    response = client.beta.chat.completions.parse(...)
    return response.choices[0].message.parsed
else:
    response = client.chat.completions.create(..., response_format={"type": "json_object"})
    data = json.loads(response.choices[0].message.content)
    return PromptClassificationResult(**data)
```

### Heuristic Regex Fallback & Keyword Bug
The heuristic regex fallback matches prompts using keyword arrays.
*   **The Original Bug**: The checks in `classify_heuristically()` checked decision keywords (`should i`, `choose`, `decide`) *before* checking code keywords (`def `, `class `, `loop`). If a prompt matched both (e.g. *"should I use a for loop or a while loop here"*), the classifier matched decision keywords first and returned `decision_making` (scoring +3).
*   **The Fix**: We reordered the conditions so that code keywords take precedence, classifying the prompt as `code_debugging` (scoring +2).
*   **The New Tradeoff**: Subjective decision-making questions about coding structures (e.g. *"Should I write a function or a class for this?"*) now trigger the code keywords first and classify as `code_debugging` instead of `decision_making`. This is an acceptable tradeoff since coding remains a lower cognitive risk (+2 weight) than life choices (+3 weight).

---

## 5. Reliability & Performance Features

### The 0.6 Confidence Fallback
If the LLM responds but yields a `confidence` score lower than `0.6` (the threshold), the system automatically routes the query to `classify_heuristically(prompt)`. Since a binary classification (convergent vs. divergent) has a random-guess baseline of `0.5`, a confidence of `< 0.6` indicates that the LLM is highly uncertain. Reverting to the deterministic, regex-based fallback avoids capturing hallucinations.

### The Two Caching Layers

```text
Prompt ──► [In-Memory LRU Cache (RAM)] ──(Miss)──► [Persistent SQLite Cache (DB)] ──(Miss)──► [LLM API Call]
                 ▲                                       │
                 └───────────────(Populate RAM)──────────┘
```

1.  **In-Memory LRU Cache (`CLASSIFIER_CACHE`)**:
    *   **Scope**: Active runtime RAM. Cleared when the server process restarts.
    *   **Limit**: Max size of 500 records. Once full, it evicts the least recently used keys.
    *   **Performance**: Sub-millisecond lookup latency.
2.  **Persistent DB Cache (`prompt_records` table)**:
    *   **Scope**: SQLite database on disk. Persistent across server restarts, active sessions, and different users.
    *   **Performance**: Low-latency (few milliseconds) file-based query.
3.  **Interaction**: On an in-memory miss, the app queries the DB using `session_store.get_cached_prompt_record(prompt)`. If a database record is found, the system instantiates it as a `PromptClassificationResult`, populates the in-memory cache with the result, and returns it.

### The Cache "Stickiness" Tradeoff
Because the database serves as a permanent cache, any classification result (including a heuristic fallback or a misclassification) becomes **sticky**. If a user submits a prompt that falls back to heuristic because the LLM API is down, that heuristic result is saved in the database. Every identical future prompt will hit the database cache and return the heuristic result, even when the LLM API is online.
*   **Defense**: This design prioritizes **cost control** (preventing expensive, repetitive LLM completions) and **extreme speed** (0ms database response). For production environments, this tradeoff would be managed by adding a `ttl` (Time-To-Live) expiration column to cache records or by implementing an admin cache eviction dashboard.

### Timing & Token Caveat
Cache hits bypass the LLM and return `latency_ms = 0` (or `None`) and `total_tokens = 0`. Any downstream reporting that calculates average latency or total token usage must ignore or handle these zeroed values, as they will skew the metrics downward.

### HTTP Error Codes & Error Handling Architecture

The backend handles failures and validation issues with specific HTTP status codes:

| HTTP Status | Trigger & Code Location | Behavior / Response |
| :--- | :--- | :--- |
| **`400 Bad Request`** | [`main.py:L242`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/app/main.py#L242) (Empty prompt submission: `prompt.strip() == ""`) | Returns `{"detail": "Prompt cannot be empty"}` |
| **`403 Forbidden`** | [`main.py:L122-L128`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/app/main.py#L122-L128) (HMAC SHA-256 session signature mismatch against `SESSION_SECRET_KEY`) | Blocks unverified or tampered session IDs |
| **`404 Not Found`** | [`main.py:L38-L88`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/app/main.py#L38-L88) (Custom 404 exception handler) | Renders dark-mode themed HTML for browser requests or JSON `{"error": "Not Found"}` for API calls |
| **`422 Unprocessable Entity`** | [`main.py:L171-L174`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/app/main.py#L171-L174) (Pydantic validation: `prompt` > 5000 chars or malformed body) | Enforces schema validation before reaching classifier |
| **`429 Too Many Requests`** | [`main.py:L149-L170`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/app/main.py#L149-L170) (In-memory Token Bucket exhausted; 10 capacity, 0.5 tokens/sec) | Returns `{"detail": "Rate limit exceeded. Try again in a few seconds."}` |
| **`500 Internal Server Error`** | [`main.py:L92-L100`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/app/main.py#L92-L100), [`classifier.py:L416`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/app/classifier.py#L416) (Global exception handler or persistent LLM retry failure) | Catches unhandled exceptions, prints stack trace, returns JSON error |

**Upstream LLM Provider Errors (OpenRouter / OpenAI)**:
* `401 Unauthorized`: Bad or expired `LLM_API_KEY`.
* `402 Payment Required`: LLM account balance depleted.
* `429 Upstream Quota`: Provider-side rate limiting.
* `502 / 503 / 504`: Provider outage or upstream gateway timeouts. (Managed via 2-attempt retry loop before failing with 500 or falling back).

---

## 6. The Evaluation Methodology

### The Overfitting & Generalization Narrative
To test the accuracy of the local heuristic fallback classifier, we built a comprehensive offline evaluation harness in [`backend/evaluation/evaluate.py`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/evaluation/evaluate.py).

```text
[300-Prompt Labeled Train Set] ──► [Heuristic Regex Tuning] ──► 95.67% Subtype Accuracy
                                                                      │
[36-Prompt Holdout Set] ────────► [Generalization Test] ─────► 52.78% Subtype Accuracy (Overfitted!)
```

1.  **Training Phase**: We compiled a 300-prompt labeled training set (`dataset_train.jsonl`) and tuned the keyword regex patterns in `classify_heuristically()` until the classifier achieved **95.67%** subtype accuracy.
2.  **Holdout Phase**: To verify generalization, we built a separate 36-prompt holdout set (`dataset_holdout.jsonl`) composed entirely of factual queries (e.g. *"Who sculpted the Statue of David?"*, *"Who composed the Magic Flute opera?"*).
3.  **The Result**: When evaluated against the holdout set, the subtype accuracy dropped to **52.78%**. 
4.  **The Discovery**: This revealed that the heuristics were overfitted to the training set's phrasing structures (which heavily utilized keywords like `"what is"`, `"where is"`, and `"define"`) and completely failed to capture alternative factual query markers like `"who sculpted"` or `"who composed"`.
5.  **The Resolution**: We updated the default fallbacks and added imperative command handling. However, we **deliberately chose not to append endless lists of specific query keywords** to make the holdout set pass. Trying to turn a regex script into a Natural Language Processing engine is an anti-pattern; fallback heuristics must remain simple, while complex phrasings are left to the LLM path.

### Classification-Level vs. Subtype-Level Accuracy
*   **Classification-Level (100% on Holdout)**: Measures whether the prompt was correctly classified as `convergent` or `divergent`. Since factual queries are all convergent, and the default fallback is convergent, the classifier scored 100% on classification accuracy.
*   **Subtype-Level (52.78% on Holdout)**: Measures whether the classifier identified the specific subtype (e.g., `factual_lookup` vs. `other`). Because 17 out of 36 prompts did not contain the training keywords, they defaulted to `other` instead of `factual_lookup`, yielding `19 / 36 = 52.78%` accuracy.
*   **Tradeoff**: Evaluating only classification-level accuracy would give a false sense of security (100%), masking the failure to identify the correct subtype, which is crucial for calculating the weights in our overreliance scoring logic.

### Exact Accuracy Metrics (`results.json`)
The following metrics are pulled directly from [`backend/evaluation/results.json`](file:///c:/Users/sriva/Desktop/prompt-classifier/backend/evaluation/results.json):

```json
{
  "metrics": {
    "overall_accuracy": 0.5278,
    "class_accuracy": 1.0,
    "subtype_accuracy": 0.5278,
    "classification": {
      "convergent": {
        "precision": 1.0,
        "recall": 1.0,
        "f1": 1.0,
        "support": 36
      }
    },
    "subtype": {
      "factual_lookup": {
        "precision": 1.0,
        "recall": 0.5278,
        "f1": 0.6909,
        "support": 36
      }
    }
  }
}
```

---

## 7. Known Limitations

1.  **LLM Error Rates**: LLMs are subject to hallucinations or subtle phrasing sensitivities. We handle this by keeping the local heuristic classifier as a baseline backup and requiring a `0.6` confidence threshold.
2.  **Fallback Weaknesses**: Regex matches cannot capture semantic context (e.g., writing a *"poem about code"* matches code keywords and misclassifies as `code_debugging` convergent instead of `divergent`). This is an acceptable limitation because the fallback is a safe, no-cost fallback that runs only when the LLM key is absent.
3.  **Non-Clinical Tool**: The point weights (+3, +2, +1, -1) and thresholds are heuristic design metrics to nudge user introspection, not a clinical behavioral diagnostic. We frame this clearly in the UI warning banners.
4.  **DB Cache Stickiness**: Erroneous classifications can persist indefinitely. We trade cache freshness for zero latency and cost control.

---

## 8. Security History

### Leaked Key Incidents & Mitigations
During the development process, an active API key was accidentally committed to the git index.
*   **Action**: The leaked key was immediately revoked and rotated.
*   **Git Cleanup**: The repository was reset, and `.env` was added to `.gitignore`.
*   **Continuous Integration**: We integrated `gitleaks` into the CI pipeline in [`.github/workflows/ci.yml`](file:///c:/Users/sriva/Desktop/prompt-classifier/.github/workflows/ci.yml):
    ```yaml
      - name: Gitleaks Scan
        uses: gitleaks/gitleaks-action@v3
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    ```
    This scans the entire commit history for secrets on pushes and pull requests, blocking builds if a leak occurs.

### `.env.example` vs. `.env`
*   [`.env.example`](file:///c:/Users/sriva/Desktop/prompt-classifier/.env.example) is committed to version control. It outlines the environment configuration keys (`LLM_API_KEY`, `LLM_BASE_URL`, `DATABASE_URL`) with placeholders so developers know how to configure the app.
*   `.env` holds the actual secrets and local SQLite paths and is ignored by git to prevent credential leaks.

---

## 9. The Provider-Agnostic Rename & Environment Harmonization

We refactored all environment variables to be strictly provider-agnostic:
*   `OPENROUTER_API_KEY` / `OPENAI_API_KEY` $\rightarrow$ `LLM_API_KEY`
*   `OPENROUTER_BASE_URL` / `OPENAI_BASE_URL` $\rightarrow$ `LLM_BASE_URL`
*   `CLASSIFIER_MODEL` (defaults to `gpt-4o-mini` or custom provider models like `nvidia/nemotron-3-super-120b-a12b:free`)

**Rationale & Test Isolation**:
1. **Single Source of Truth**: The OpenAI Python SDK acts as an open protocol client. By configuring the `base_url` parameter, it connects to any OpenAI-compatible API gateway (OpenRouter, local Ollama, Azure, etc.). Hardcoding "OpenAI" or "OpenRouter" implied vendor lock-in.
2. **Environment Variable Harmonization**: Legacy fallback aliases (`OPENAI_API_KEY`, `key`, `OPENAI_BASE_URL`) were consolidated and cleaned across `.env`, `classifier.py`, and `conftest.py`. This ensures tests run in clean isolation without ambient `.env` variables leaking into unit mocks.

---

## 10. Git History & Engineering Process

We broke the codebase updates into granular, single-purpose commits to maintain clean diffs and ease rollback.

### Pushed Commit History (`git log --oneline`)
```text
aae4d18 redesign frontend layout, add charts, and show latency/tokens
6ce93f1 add response caching, confidence-threshold fallback, and latency/token logging
af57509 add structured explanations, reflection prompts, and Guilford divergent subtypes to classification output
3eb926a fix heuristic ordering bug for code vs decision prompts and add regression tests
b2eeab7 add evaluation script and train/holdout dataset splits
bd6d62f add gitleaks scan job to ci workflow
abaabcd rename openrouter-specific env vars to be provider agnostic
22af48b update readme tech stack overview, caching notes, and instructions
1e942fc clean up remaining standalone references to OpenAI in comments and docs
8bbb24c document persistent database cache limitations and stickiness tradeoff
```

### Verification Pipeline
After applying each commit, we ran the test suite (`pytest` and `vitest`) before moving to the next commit. This ensured that no commit left the codebase in a broken or non-compilable state, maintaining architectural integrity.

---

## 11. Anticipated Interview Questions & Model Answers

### Architecture
1.  **Q: Why choose SQLite over a client-server database like PostgreSQL?**
    *   *Answer*: SQLite is serverless and self-contained. Since our application tracks individual developer sessions locally, using SQLite eliminates the need for database server provisioning and networking setup, making the tool instantly executable with a simple `alembic upgrade head` command.
2.  **Q: Why implement an in-memory LRU cache if you already have a persistent SQLite cache?**
    *   *Answer*: Reading from SQLite requires disk I/O, which, although fast, still takes several milliseconds and blocks event loop threads on high concurrency. The in-memory LRU cache (`CLASSIFIER_CACHE`) resolves repetitive requests in sub-milliseconds in RAM, while the SQLite DB handles persistence across server restarts.
3.  **Q: How does the system handle concurrent writes to the database in SQLite?**
    *   *Answer*: FastAPI is configured with standard SQLite connection flags `check_same_thread=False` and handles DB session context cleanly per request. SQLite's write-ahead logging (WAL) or standard locking mechanisms handle write concurrency at our current local scale. If scaling to multiple concurrent users, we would swap the SQLite engine for PostgreSQL.

### Evaluation
4.  **Q: Why did your accuracy drop from 95% to 52% on the holdout set?**
    *   *Answer*: The training set was primarily built on prompts matching our regex patterns. The holdout set tested generalization using factual prompts with different phrasing structures (e.g., *"Who composed..."*). The drop to 52.78% exposed that the keyword regexes were overfitted to the training set's vocabulary.
5.  **Q: Why did you decide NOT to add keywords like "Who composed" to fix the holdout accuracy drop?**
    *   *Answer*: Adding specific keywords would simply overfit the heuristic model to the holdout set. Fallback heuristics have structural limitations; trying to build a full NLP parser with regexes is an anti-pattern. We chose to accept the fallback error rate and rely on the LLM path for complex query parsing.
6.  **Q: Why was F1 score a better evaluation metric than overall accuracy for the holdout set?**
    *   *Answer*: In our holdout set, all 36 prompts were convergent factual queries. If we only evaluated binary classification accuracy, we would see 100%. The F1 score for `factual_lookup` (0.6909) revealed that the classifier missed 47% of the factual lookups, classifying them as `other`, which directly affects the overreliance point tracking.

### Limitations & Tradeoffs
7.  **Q: How would you defend the DB cache stickiness tradeoff in a production audit?**
    *   *Answer*: The cache saves substantial API token costs and reduces response latency to 0ms. While misclassifications can get stuck, the impact is low since the tool is for developer self-reflection, not clinical diagnostics. In production, we would add a TTL expiration or a manual "recategorize" button to evict the key.
8.  **Q: Why does the code-precedence regex ordering fix make subjective decision-making prompts about code misclassify as coding?**
    *   *Answer*: Because keyword matching cannot parse semantic intent. If a prompt matches both code keywords (`function`) and decision keywords (`should I`), one must take precedence. We prioritized coding because it carries a lower overreliance score weight (+2 vs +3), reducing the risk of triggering false overreliance warnings.

### Future Work & Scale
9.  **Q: What is the first bottleneck you would hit if scaling to 10,000 active users?**
    *   *Answer*: Database writes. SQLite locks the entire database file during writes. Under high write concurrency, FastAPI requests would block. We would migrate the database to PostgreSQL and transition the in-memory cache to a shared Redis cluster.
10. **Q: How would you improve the fallback classifier without calling an LLM API?**
    *   *Answer*: We could run a lightweight, local sentence-transformer model (such as `all-MiniLM-L6-v2`) exported to ONNX format. This would allow us to compute semantic embeddings of the prompts locally in Python and classify them via cosine similarity against reference embeddings, removing regex dependency.

### Extension
11. **Q: How would you add a 6th classification subtype (e.g. "translation")?**
    *   *Answer*: I would add `"translation"` to the `subtype` Literal in `classifier.py`, run an Alembic migration to update the SQLite database schema checks, update the frontend `types.ts` interface, and add the appropriate point weight configuration in `calculate_overreliance()`.
12. **Q: How would you isolate session histories if user authentication is added?**
    *   *Answer*: I would introduce an OAuth2 authentication dependency in FastAPI, add a `user_id` column to the `sessions` database model, and ensure that all session history queries filter records by both `session_id` and the authenticated `user_id`.

### Git & Security
13. **Q: What is Gitleaks and how does it prevent API key leaks?**
    *   *Answer*: Gitleaks is a static analysis tool that scans git repositories for secrets (like high-entropy strings, private keys, and API credentials). By running it as a GitHub Action on every pull request, we block any commits containing exposed keys from merging.
14. **Q: Why was it important to split the caching layer and structured explanations into separate commits (2a and 2b)?**
    *   *Answer*: Separating them isolated the pull requests. Commit 2a introduced only the backend timing, cache tables, and performance logging. Commit 2b added the complex structured Pydantic models, reflection prompts, and frontend UI changes. This made code reviews easier and simplified testing.
15. **Q: Why do we keep `.env.example` in git but ignore `.env`?**
    *   *Answer*: `.env.example` serves as the configuration template for the team, documenting which variables are required without containing secrets. `.env` stores the actual credentials and is ignored to prevent accidental leaks.

### Error Handling, Rate Limiting & Session Security
16. **Q: How does your rate limiting work, and what HTTP status code does it return?**
    *   *Answer*: In `main.py`, we implement an in-memory Token Bucket algorithm dependency on the `/api/classify` endpoint. It has a burst capacity of 10 tokens and refills at 0.5 tokens/sec (1 token every 2 seconds) per client IP (extracting `X-Forwarded-For` when behind proxies). When exhausted, it returns `HTTP 429 Too Many Requests` with `{"detail": "Rate limit exceeded. Try again in a few seconds."}`.
17. **Q: How do you verify session authenticity without full user accounts?**
    *   *Answer*: We generate cryptographically signed session IDs in `main.py` using HMAC SHA-256 (`<raw_token>.<signature>`) signed against `SESSION_SECRET_KEY`. Any tampered or invalid session ID triggers `HTTP 403 Forbidden` (`Session verification failed`), preventing unauthorized database queries while keeping the app lightweight and registration-free.
18. **Q: What HTTP status codes does the API return across all scenarios?**
    *   *Answer*: The API returns standard HTTP status codes:
        * `200 OK`: Successful prompt classification, session retrieval, or deletion.
        * `400 Bad Request`: Empty or whitespace-only prompt strings.
        * `403 Forbidden`: HMAC session signature verification failure.
        * `404 Not Found`: Unknown endpoint routes (serves styled dark-mode HTML for browsers or JSON for API calls).
        * `422 Unprocessable Entity`: Pydantic payload validation error (e.g. prompt exceeding 5,000 characters).
        * `429 Too Many Requests`: Token bucket rate limit reached.
        * `500 Internal Server Error`: Global unhandled exceptions or LLM retry exhaustion.

---

## 12. Weak Spots to Rehearse

1.  **DB Cache Stickiness**: If pressed on how to clear bad cache entries, suggest adding a cache eviction API (`POST /api/cache/evict`) or adding a `cached_at` timestamp column to SQL database records to enforce a sliding TTL expiration (e.g. 7 days).
2.  **Subjectivity of Guilford Metadata**: The LLM generates fields like `creative_freedom_score` and `factual_dependency`. These are highly subjective. Rehearse defending them as **reflective visual signals** rather than clinical data points—their purpose is to help the user pause and think.
3.  **Low Fallback Subtype Accuracy (52.78%)**: If asked why 52.78% accuracy is acceptable, state plainly that the local heuristic is a *fallback*. The primary classification path is the LLM; the fallback is only intended to keep the app running gracefully when the API key is missing or offline.
