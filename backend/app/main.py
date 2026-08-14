import os
import time
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from . import session_store
from .classifier import classify_prompt, PromptClassificationResult
from .overreliance import calculate_overreliance

load_dotenv()

app = FastAPI(title="Prompt Classifier API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    """
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
    prompt: str
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

@app.post("/api/classify", response_model=ClassifyResponse, dependencies=[Depends(rate_limit)])
def classify(request: ClassifyRequest):
    """
    Submits a user prompt for classification, records it in the database session,
    and returns the result with a rolling overreliance analysis score.
    """
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
        reasoning=result.reasoning
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
        session_summary=summary
    )

@app.get("/api/session/{session_id}", response_model=SessionHistoryResponse)
def get_session(session_id: str):
    """
    Retrieves the complete history of prompts and classification summaries for a given session.
    """
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
            "created_at": r.created_at
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
    session_store.clear_session_history(session_id)
    return {"message": "Session history cleared successfully"}
