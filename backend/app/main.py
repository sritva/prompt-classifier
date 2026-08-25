import os
import time
import json
import hmac
import hashlib
import secrets
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from . import session_store
from .classifier import classify_prompt, PromptClassificationResult
from .overreliance import calculate_overreliance

load_dotenv()

app = FastAPI(title="Prompt Classifier API")

# Configure secure CORS origins
allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]
allow_credentials = True
if "*" in allowed_origins:
    allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(404)
async def custom_404_handler(request: Request, exc: Exception):
    if "text/html" in request.headers.get("accept", "").lower():
        html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>404 Not Found</title>
            <style>
                body {
                    background-color: #181716;
                    color: #E3DFD5;
                    font-family: system-ui, -apple-system, sans-serif;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    margin: 0;
                }
                h1 {
                    font-size: 3rem;
                    margin: 0 0 1rem 0;
                    color: #D49B55;
                }
                p {
                    font-size: 1.1rem;
                    color: #7D786F;
                    margin: 0 0 2rem 0;
                }
                a {
                    color: #E3DFD5;
                    font-family: monospace;
                    text-decoration: underline;
                }
            </style>
        </head>
        <body>
            <h1>404</h1>
            <p>The requested page or resource could not be found.</p>
            <a href="/">Go to Dashboard</a>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content, status_code=404)
    return JSONResponse(
        status_code=404,
        content={"error": "Not Found", "message": "The requested API endpoint does not exist."}
    )

import traceback

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print("=== GLOBAL EXCEPTION HANDLER ===")
    traceback.print_exc()
    print("================================")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal Server Error: {str(exc)}"}
    )


SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY")
if not SESSION_SECRET_KEY:
    if os.getenv("ENVIRONMENT") == "production" or os.getenv("VERCEL") == "1":
        raise RuntimeError("SESSION_SECRET_KEY environment variable is required in production.")
    SESSION_SECRET_KEY = "dev-secret-key-change-in-production-1234567890"

def generate_signed_session_id() -> str:
    raw_id = secrets.token_urlsafe(16)
    sig = hmac.new(SESSION_SECRET_KEY.encode(), raw_id.encode(), hashlib.sha256).hexdigest()
    return f"{raw_id}.{sig}"

def verify_session_id(signed_id: str) -> bool:
    try:
        raw_id, sig = signed_id.rsplit(".", 1)
        expected_sig = hmac.new(SESSION_SECRET_KEY.encode(), raw_id.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected_sig)
    except Exception:
        return False

def check_session_id(session_id: str):
    if not verify_session_id(session_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session verification failed. Invalid or malformed session identifier."
        )

class TokenBucket:
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()

    def consume(self, tokens: int = 1) -> bool:
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

classify_buckets = {}

def rate_limit(request: Request):
    """
    In-memory rate limiter bucket dependency for /api/classify.
    Capacity: 10 requests, refills 1 token every 2 seconds (0.5 tokens/sec).
    Supports X-Forwarded-For to work correctly behind reverse proxies.
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"
    
    if client_ip not in classify_buckets:
        classify_buckets[client_ip] = TokenBucket(capacity=10, refill_rate=0.5)
    
    bucket = classify_buckets[client_ip]
    if not bucket.consume(1):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again in a few seconds."
        )

class ClassifyRequest(BaseModel):
    prompt: str = Field(..., max_length=5000, description="The prompt text to classify (max 5000 characters)")
    session_id: str

class SessionSummary(BaseModel):
    total_prompts: int
    convergent_percentage: float
    divergent_percentage: float
    overreliance_score: int
    overreliance_signal: str

class ClassifyResponse(BaseModel):
    id: Optional[int] = None
    prompt: str
    classification: str
    subtype: Optional[str] = None
    confidence: float
    reasoning: str
    created_at: datetime
    latency_ms: Optional[int] = None
    total_tokens: Optional[int] = None
    explanation_details: Optional[dict] = None
    reflection_prompt: Optional[str] = None
    session_summary: SessionSummary

class SessionHistoryResponse(BaseModel):
    session_id: str
    history: List[dict]
    session_summary: SessionSummary

def build_session_summary(history) -> SessionSummary:
    total = len(history)
    if total == 0:
        return SessionSummary(
            total_prompts=0,
            convergent_percentage=0.0,
            divergent_percentage=0.0,
            overreliance_score=0,
            overreliance_signal="none"
        )
        
    convergent_count = sum(1 for r in history if r.classification == "convergent")
    divergent_count = sum(1 for r in history if r.classification == "divergent")
    
    conv_pct = round((convergent_count / total) * 100, 1)
    div_pct = round((divergent_count / total) * 100, 1)
    
    overreliance_data = calculate_overreliance(history)
    
    return SessionSummary(
        total_prompts=total,
        convergent_percentage=conv_pct,
        divergent_percentage=div_pct,
        overreliance_score=overreliance_data["score"],
        overreliance_signal=overreliance_data["signal"]
    )

@app.post("/api/session")
def create_session():
    """
    Generates and returns a new signed session ID.
    """
    return {"session_id": generate_signed_session_id()}

@app.post("/api/classify", response_model=ClassifyResponse, dependencies=[Depends(rate_limit)])
def classify(request: ClassifyRequest):
    """
    Submits a user prompt for classification, records it in the database session,
    and returns the result with a rolling overreliance analysis score.
    """
    check_session_id(request.session_id)
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")
        
    try:
        result = classify_prompt(request.prompt)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Classification error: {str(e)}"
        )
        
    record = session_store.add_prompt_record(
        session_id=request.session_id,
        prompt=request.prompt,
        classification=result.classification,
        subtype=result.subtype,
        confidence=result.confidence,
        reasoning=result.reasoning,
        latency_ms=result.latency_ms,
        total_tokens=result.total_tokens,
        explanation_details=json.dumps(result.explanation_details.model_dump()) if result.explanation_details else None,
        reflection_prompt=result.reflection_prompt
    )
    
    history = session_store.get_session_history(request.session_id)
    summary = build_session_summary(history)
    
    return ClassifyResponse(
        id=record.id,
        prompt=record.prompt,
        classification=record.classification,
        subtype=record.subtype,
        confidence=record.confidence,
        reasoning=record.reasoning,
        created_at=record.created_at,
        latency_ms=record.latency_ms,
        total_tokens=record.total_tokens,
        explanation_details=json.loads(record.explanation_details) if record.explanation_details else None,
        reflection_prompt=record.reflection_prompt,
        session_summary=summary
    )

@app.get("/api/session/{session_id}", response_model=SessionHistoryResponse)
def get_session(session_id: str):
    """
    Retrieves the complete history of prompts and classification summaries for a given session.
    """
    check_session_id(session_id)
    history = session_store.get_session_history(session_id)
    summary = build_session_summary(history)
    
    history_list = []
    for r in history:
        history_list.append({
            "id": r.id,
            "prompt": r.prompt,
            "classification": r.classification,
            "subtype": r.subtype,
            "confidence": r.confidence,
            "reasoning": r.reasoning,
            "created_at": r.created_at,
            "latency_ms": r.latency_ms,
            "total_tokens": r.total_tokens,
            "explanation_details": json.loads(r.explanation_details) if r.explanation_details else None,
            "reflection_prompt": r.reflection_prompt
        })
        
    return SessionHistoryResponse(
        session_id=session_id,
        history=history_list,
        session_summary=summary
    )

@app.delete("/api/session/{session_id}")
def delete_session(session_id: str):
    """
    Clears all recorded prompts and resets the cognitive scoring context for the session.
    """
    check_session_id(session_id)
    session_store.clear_session_history(session_id)
    return {"message": "Session history cleared successfully"}
