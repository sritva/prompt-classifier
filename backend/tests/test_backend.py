import os
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest

from app.classifier import classify_heuristically, classify_prompt, PromptClassificationResult
from app.overreliance import calculate_overreliance
from app import session_store
from app.models import PromptRecord

# 1. Test Heuristic Fallback Path
def test_heuristic_fallback_decision_making():
    res = classify_heuristically("Should I take the new job offer or stay at my current one?")
    assert res.classification == "convergent"
    assert res.subtype == "decision_making"
    assert "decision-making" in res.reasoning

def test_heuristic_fallback_code_debugging():
    res = classify_heuristically("Why does my Python function return None? def my_func(): pass")
    assert res.classification == "convergent"
    assert res.subtype == "code_debugging"

def test_heuristic_fallback_computation():
    res = classify_heuristically("Solve 25 * 4 + 10")
    assert res.classification == "convergent"
    assert res.subtype == "computation"

def test_heuristic_fallback_factual_lookup():
    res = classify_heuristically("What is the capital of Japan?")
    assert res.classification == "convergent"
    assert res.subtype == "factual_lookup"

def test_heuristic_fallback_divergent():
    res = classify_heuristically("Write a creative poem about the wind.")
    assert res.classification == "divergent"
    assert res.subtype is None

# 2. Test Overreliance Scoring
def test_overreliance_high():
    # 3 decision making prompts: 3 * 3 = 9 (>= 8 -> high)
    now = datetime.now(timezone.utc)
    history = [
        PromptRecord(classification="convergent", subtype="decision_making", created_at=now - timedelta(minutes=1)),
        PromptRecord(classification="convergent", subtype="decision_making", created_at=now - timedelta(minutes=2)),
        PromptRecord(classification="convergent", subtype="decision_making", created_at=now - timedelta(minutes=3)),
    ]
    res = calculate_overreliance(history, reference_time=now)
    assert res["score"] == 9
    assert res["signal"] == "high"

def test_overreliance_moderate_mixed():
    # 1 decision making (+3), 1 coding (+2), 1 divergent (-1) -> score 4 (>=2 and <5 is low? Wait, 2-4 is low, 5-7 is moderate, >=8 is high. Let's check thresholds:
    # score >= 8 -> high, >= 5 -> moderate, >= 2 -> low, < 2 -> none)
    # So score 4 should be "low". Let's verify.
    now = datetime.now(timezone.utc)
    history = [
        PromptRecord(classification="convergent", subtype="decision_making", created_at=now - timedelta(minutes=1)),
        PromptRecord(classification="convergent", subtype="code_debugging", created_at=now - timedelta(minutes=2)),
        PromptRecord(classification="divergent", subtype=None, created_at=now - timedelta(minutes=3)),
    ]
    res = calculate_overreliance(history, reference_time=now)
    assert res["score"] == 4
    assert res["signal"] == "low"

def test_overreliance_moderate_exact():
    # 2 decision making (+6), 1 divergent (-1) -> 5 (moderate)
    now = datetime.now(timezone.utc)
    history = [
        PromptRecord(classification="convergent", subtype="decision_making", created_at=now - timedelta(minutes=1)),
        PromptRecord(classification="convergent", subtype="decision_making", created_at=now - timedelta(minutes=2)),
        PromptRecord(classification="divergent", subtype=None, created_at=now - timedelta(minutes=3)),
    ]
    res = calculate_overreliance(history, reference_time=now)
    assert res["score"] == 5
    assert res["signal"] == "moderate"

def test_overreliance_all_divergent():
    now = datetime.now(timezone.utc)
    history = [
        PromptRecord(classification="divergent", subtype=None, created_at=now - timedelta(minutes=1)),
        PromptRecord(classification="divergent", subtype=None, created_at=now - timedelta(minutes=2)),
    ]
    res = calculate_overreliance(history, reference_time=now)
    assert res["score"] == 0
    assert res["signal"] == "none"

def test_overreliance_outside_window():
    now = datetime.now(timezone.utc)
    history = [
        PromptRecord(classification="convergent", subtype="decision_making", created_at=now - timedelta(minutes=15)),
        PromptRecord(classification="convergent", subtype="decision_making", created_at=now - timedelta(minutes=2)),
    ]
    # Only 1 in-window decision making -> score 3 (low)
    res = calculate_overreliance(history, reference_time=now)
    assert res["score"] == 3
    assert res["signal"] == "low"

# 3. Test Session CRUD
def test_session_crud():
    session_id = "test-session-123"
    
    # Get or create
    sess = session_store.get_or_create_session(session_id)
    assert sess.session_id == session_id
    
    # Add record
    rec = session_store.add_prompt_record(
        session_id=session_id,
        prompt="Explain quantum mechanics",
        classification="convergent",
        subtype="factual_lookup",
        confidence=0.9,
        reasoning="Simple factual query."
    )
    assert rec.id is not None
    assert rec.prompt == "Explain quantum mechanics"
    
    # Get history
    history = session_store.get_session_history(session_id)
    assert len(history) == 1
    assert history[0].id == rec.id
    
    # Clear history
    session_store.clear_session_history(session_id)
    history_after = session_store.get_session_history(session_id)
    assert len(history_after) == 0

# 4. Test API Endpoints & Mocking
@patch("app.classifier.OpenAI")
def test_api_classify_openai_success(mock_openai_class, client):
    # Mock successful OpenAI structured completion
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    
    mock_parsed_result = PromptClassificationResult(
        classification="convergent",
        confidence=0.98,
        reasoning="Identified as a factual lookup prompt.",
        subtype="factual_lookup"
    )
    mock_choice = MagicMock()
    mock_choice.message.parsed = mock_parsed_result
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.beta.chat.completions.parse.return_value = mock_response

    # Temporarily set API key to force OpenAI path
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-real-key-placeholder"}):
        response = client.post(
            "/api/classify",
            json={"prompt": "What is the boiling point of helium?", "session_id": "test-api-session"}
        )
        
    assert response.status_code == 200
    data = response.json()
    assert data["classification"] == "convergent"
    assert data["subtype"] == "factual_lookup"
    assert data["confidence"] == 0.98
    assert data["session_summary"]["total_prompts"] == 1
    assert data["session_summary"]["convergent_percentage"] == 100.0

def test_api_classify_fallback_success(client):
    # Explicitly verify fallback occurs when key is not set/placeholder
    with patch.dict(os.environ, {"OPENAI_API_KEY": "placeholder"}):
        response = client.post(
            "/api/classify",
            json={"prompt": "Write a story about a dragon.", "session_id": "test-fallback-session"}
        )
        
    assert response.status_code == 200
    data = response.json()
    assert data["classification"] == "divergent"
    assert data["subtype"] is None
    assert data["session_summary"]["total_prompts"] == 1

@patch("app.classifier.OpenAI")
def test_api_classify_openai_retry_and_fail(mock_openai_class, client):
    # Mock OpenAI client always raising exception to test retry behavior
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    mock_client.beta.chat.completions.parse.side_effect = Exception("OpenAI API Down")

    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-real-key-placeholder"}):
        response = client.post(
            "/api/classify",
            json={"prompt": "What is 2+2?", "session_id": "test-fail-session"}
        )
        
    # Standard sync TestClient allows us to capture the 500 error
    assert response.status_code == 500
    assert "Classification error" in response.json()["detail"]
    # Check that client was called twice (initial attempt + 1 retry)
    assert mock_client.beta.chat.completions.parse.call_count == 2

def test_api_session_history_and_clear(client):
    session_id = "test-history-clear"
    
    # Populate history
    session_store.add_prompt_record(
        session_id=session_id,
        prompt="Factual Lookup Prompt",
        classification="convergent",
        subtype="factual_lookup",
        confidence=0.9,
        reasoning="Reason"
    )
    
    # GET session history
    response = client.get(f"/api/session/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["history"]) == 1
    assert data["session_summary"]["total_prompts"] == 1
    
    # DELETE session history
    del_response = client.delete(f"/api/session/{session_id}")
    assert del_response.status_code == 200
    
    # Verify cleared
    get_again = client.get(f"/api/session/{session_id}")
    assert len(get_again.json()["history"]) == 0
