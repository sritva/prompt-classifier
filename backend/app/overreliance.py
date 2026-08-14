from datetime import datetime, timezone, timedelta
from typing import TypedDict, Literal

class OverrelianceResult(TypedDict):
    score: int
    signal: Literal["high", "moderate", "low", "none"]

def calculate_overreliance(history: list, reference_time: datetime | None = None) -> OverrelianceResult:
    """
    Calculates the overreliance score within a 10-minute rolling window.
    - decision_making: +3 points
    - code_debugging: +2 points
    - computation, factual_lookup, other (convergent): +1 point each
    - divergent: -1 point each (floor of 0)
    
    Thresholds:
    - >= 8: high
    - >= 5: moderate
    - >= 2: low
    - < 2: none
    """
    if reference_time is None:
        reference_time = datetime.now(timezone.utc)
        
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)
        
    cutoff = reference_time - timedelta(minutes=10)
    score = 0
    
    for record in history:
        created_at = record.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
            
        if created_at >= cutoff:
            if record.classification == "convergent":
                if record.subtype == "decision_making":
                    score += 3
                elif record.subtype == "code_debugging":
                    score += 2
                else:
                    score += 1
            elif record.classification == "divergent":
                score -= 1

    if score < 0:
        score = 0
        
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
