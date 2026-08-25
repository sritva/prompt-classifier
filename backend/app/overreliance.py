from datetime import datetime, timezone, timedelta
from typing import TypedDict, Literal

class OverrelianceResult(TypedDict):
    score: int
    signal: Literal["high", "moderate", "low", "none"]

def calculate_overreliance(history: list, reference_time: datetime | None = None) -> OverrelianceResult:
    if reference_time is None:
        reference_time = datetime.now(timezone.utc)
        
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)
        
    cutoff = reference_time - timedelta(minutes=10)
    raw_score = 0.0
    
    for record in history:
        created_at = record.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
            
        if created_at >= cutoff:
            confidence = getattr(record, "confidence", 1.0)
            if confidence is None:
                confidence = 1.0
                
            if record.classification == "convergent":
                if record.subtype == "decision_making":
                    raw_score += 3.0 * confidence
                elif record.subtype == "code_debugging":
                    raw_score += 2.0 * confidence
                else:
                    raw_score += 1.0 * confidence
            elif record.classification == "divergent":
                raw_score -= 1.0

    score = int(round(max(0.0, raw_score)))
        
    if score >= 8:
        signal = "high"
    elif score >= 5:
        signal = "moderate"
    elif score >= 2:
        signal = "low"
    else:
        signal = "none"
        
    return {
        "score": score,
        "signal": signal
    }

