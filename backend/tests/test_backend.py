import os
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest

from app.classifier import classify_heuristically, classify_prompt, PromptClassificationResult
from app.main import generate_signed_session_id
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

def test_heuristic_fallback_ordering_bug():
    # Prompt matches both decision ("should I") and code ("loop" or "while") keywords
    res1 = classify_heuristically("should I use a for loop or a while loop here")
    assert res1.classification == "convergent"
    assert res1.subtype == "code_debugging"

    res2 = classify_heuristically("Should I write a function or a class for this?")
    assert res2.classification == "convergent"
    assert res2.subtype == "code_debugging"

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
    assert res.subtype == "originality"

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
    with patch.dict(os.environ, {"LLM_API_KEY": "sk-real-key-placeholder"}):
        session_id = generate_signed_session_id()
        response = client.post(
            "/api/classify",
            json={"prompt": "What is the boiling point of helium?", "session_id": session_id}
        )
        
    assert response.status_code == 200
    data = response.json()
    assert data["classification"] == "convergent"
    assert data["subtype"] == "factual_lookup"
    assert data["confidence"] == 0.98
    assert data["session_summary"]["total_prompts"] == 1
    assert data["session_summary"]["convergent_percentage"] == 100.0
    assert "latency_ms" in data
    assert "total_tokens" in data
    assert data["latency_ms"] is not None

@patch("app.classifier.OpenAI")
def test_api_classify_custom_endpoint_success(mock_openai_class, client):
    # Mock successful custom endpoint (OpenRouter) JSON-mode completion
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    
    mock_choice = MagicMock()
    # Return JSON matching the schema
    mock_choice.message.content = '{"classification": "convergent", "confidence": 0.95, "reasoning": "Nemotron response.", "subtype": "computation"}'
    
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    with patch.dict(os.environ, {
        "LLM_API_KEY": "sk-or-v1-some-key",
        "LLM_BASE_URL": "https://openrouter.ai/api/v1",
        "CLASSIFIER_MODEL": "nvidia/nemotron-3-super-120b-a12b:free"
    }):
        session_id = generate_signed_session_id()
        response = client.post(
            "/api/classify",
            json={"prompt": "Solve 2+2", "session_id": session_id}
        )
        
    assert response.status_code == 200
    data = response.json()
    assert data["classification"] == "convergent"
    assert data["subtype"] == "computation"
    assert data["confidence"] == 0.95
    assert data["reasoning"] == "Nemotron response."
    assert mock_client.chat.completions.create.call_count == 1


def test_api_classify_fallback_success(client):
    # Explicitly verify fallback occurs when key is not set/placeholder
    with patch.dict(os.environ, {"LLM_API_KEY": "placeholder"}):
        session_id = generate_signed_session_id()
        response = client.post(
            "/api/classify",
            json={"prompt": "Write a story about a dragon.", "session_id": session_id}
        )
        
    assert response.status_code == 200
    data = response.json()
    assert data["classification"] == "divergent"
    assert data["subtype"] == "originality"
    assert data["session_summary"]["total_prompts"] == 1

@patch("app.classifier.OpenAI")
def test_api_classify_openai_retry_and_fail(mock_openai_class, client):
    # Mock OpenAI client always raising exception to test retry behavior
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    mock_client.beta.chat.completions.parse.side_effect = Exception("OpenAI API Down")

    with patch.dict(os.environ, {"LLM_API_KEY": "sk-real-key-placeholder"}):
        session_id = generate_signed_session_id()
        response = client.post(
            "/api/classify",
            json={"prompt": "What is 2+2?", "session_id": session_id}
        )
        
    # Standard sync TestClient allows us to capture the 500 error
    assert response.status_code == 500
    assert "Classification error" in response.json()["detail"]
    # Check that client was called twice (initial attempt + 1 retry)
    assert mock_client.beta.chat.completions.parse.call_count == 2

def test_api_session_history_and_clear(client):
    session_id = generate_signed_session_id()
    
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

@patch("app.classifier.OpenAI")
def test_confidence_threshold_fallback(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    
    mock_parsed_result = PromptClassificationResult(
        classification="convergent",
        confidence=0.4,
        reasoning="Factual query but not sure.",
        subtype="factual_lookup"
    )
    mock_choice = MagicMock()
    mock_choice.message.parsed = mock_parsed_result
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.beta.chat.completions.parse.return_value = mock_response

    with patch.dict(os.environ, {"LLM_API_KEY": "sk-real-key-placeholder"}):
        res = classify_prompt("What is the capital of France?")
        
    assert res.classification == "convergent"
    assert res.subtype == "factual_lookup"
    assert res.confidence >= 0.65
    assert "(LLM confidence below threshold, using heuristic fallback)" in res.reasoning

@patch("app.classifier.OpenAI")
def test_prompt_caching(mock_openai_class):
    from app.classifier import CLASSIFIER_CACHE
    CLASSIFIER_CACHE.clear()

    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    
    mock_parsed_result = PromptClassificationResult(
        classification="convergent",
        confidence=0.9,
        reasoning="Factual query.",
        subtype="factual_lookup"
    )
    mock_choice = MagicMock()
    mock_choice.message.parsed = mock_parsed_result
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.beta.chat.completions.parse.return_value = mock_response

    with patch.dict(os.environ, {"LLM_API_KEY": "sk-real-key-placeholder"}):
        res1 = classify_prompt("What is the capital of France?")
        res2 = classify_prompt("What is the capital of France?")
        
    assert res1 == res2
    assert mock_client.beta.chat.completions.parse.call_count == 1

@patch("app.classifier.OpenAI")
def test_cache_invalidation_on_version_bump(mock_openai_class):
    from app.classifier import CLASSIFIER_CACHE
    import app.classifier as classifier_module
    from app import session_store
    
    CLASSIFIER_CACHE.clear()
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    
    mock_parsed_result = PromptClassificationResult(
        classification="convergent",
        confidence=0.9,
        reasoning="Factual query.",
        subtype="factual_lookup"
    )
    mock_choice = MagicMock()
    mock_choice.message.parsed = mock_parsed_result
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.beta.chat.completions.parse.return_value = mock_response

    test_prompt = "What is the capital of Mars?"
    session_store.add_prompt_record(
        session_id="test-cache-sess.sig",
        prompt=test_prompt,
        classification="convergent",
        subtype="other",
        confidence=0.5,
        reasoning="Old version classification",
        classifier_version="1.0.0"
    )
    
    with patch.dict(os.environ, {"LLM_API_KEY": "sk-real-key-placeholder"}):
        res = classifier_module.classify_prompt(test_prompt)
        
    assert res.subtype == "factual_lookup"
    assert mock_client.beta.chat.completions.parse.call_count == 1



def test_api_session_creation(client):
    response = client.post("/api/session")
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert "." in data["session_id"]

def test_api_session_verification_failure(client):
    # Unsigned session ID
    response = client.get("/api/session/invalid-session-id")
    assert response.status_code == 403
    assert "Session verification failed" in response.json()["detail"]

    # Invalid signature
    response2 = client.post(
        "/api/classify",
        json={"prompt": "Hello", "session_id": "someid.invalidsig"}
    )
    assert response2.status_code == 403

def test_api_classify_prompt_length_limit(client):
    session_id = generate_signed_session_id()
    long_prompt = "a" * 5001
    response = client.post(
        "/api/classify",
        json={"prompt": long_prompt, "session_id": session_id}
    )
    assert response.status_code == 422


@pytest.mark.parametrize("prompt,expected_class,expected_subtype", [
    ("Who composed the Magic Flute opera?", "convergent", "factual_lookup"),
    ("Who sculpted the Statue of David?", "convergent", "factual_lookup"),
    ("Who directed the film Inception?", "convergent", "factual_lookup"),
    ("Who choreographed the Nutcracker ballet?", "convergent", "factual_lookup"),
    ("Who engineered the Golden Gate Bridge?", "convergent", "factual_lookup"),
    ("Who designed the Eiffel Tower?", "convergent", "factual_lookup"),
    ("What is the freezing point of mercury?", "convergent", "factual_lookup"),
    ("What is the average height of a giraffe?", "convergent", "factual_lookup"),
    ("What is the lifespan of a housefly?", "convergent", "factual_lookup"),
    ("What is the escape velocity of Earth?", "convergent", "factual_lookup"),
    ("What is the carrying capacity of a Boeing 747?", "convergent", "factual_lookup"),
    ("What is the focal length of a standard portrait lens?", "convergent", "factual_lookup"),
    ("How many keys are on a standard piano?", "convergent", "factual_lookup"),
    ("How many bones are in the human foot?", "convergent", "factual_lookup"),
    ("How many stripes are on the US flag?", "convergent", "factual_lookup"),
    ("How many chambers are in a human heart?", "convergent", "factual_lookup"),
    ("How many players are on a soccer field?", "convergent", "factual_lookup"),
    ("How many colors are in a rainbow?", "convergent", "factual_lookup"),
    ("In what year was the Magna Carta signed?", "convergent", "factual_lookup"),
    ("Identify the first element on the periodic table.", "convergent", "factual_lookup"),
    ("Specify the location of the ancient city of Petra.", "convergent", "factual_lookup"),
    ("Name the writer of Sherlock Holmes.", "convergent", "factual_lookup"),
    ("State the chemical composition of bronze.", "convergent", "factual_lookup"),
    ("Define the term photosynthesis.", "convergent", "factual_lookup"),
    ("List the base units of the SI system.", "convergent", "factual_lookup"),
    ("Divide 1500 by 25 and multiply by 4.", "convergent", "computation"),
    ("Solve the system: x + y = 10, x - y = 2.", "convergent", "computation"),
    ("Fix this regex that fails to match valid email addresses.", "convergent", "code_debugging"),
])
def test_known_misclassification_regressions(prompt, expected_class, expected_subtype):
    res = classify_heuristically(prompt)
    assert res.classification == expected_class
    assert res.subtype == expected_subtype
    assert res.confidence >= 0.65


def test_overreliance_confidence_downweighting():
    now = datetime.now(timezone.utc)
    low_conf_history = [
        PromptRecord(classification="convergent", subtype="decision_making", confidence=0.3, created_at=now - timedelta(minutes=1)),
        PromptRecord(classification="convergent", subtype="decision_making", confidence=0.4, created_at=now - timedelta(minutes=2)),
        PromptRecord(classification="convergent", subtype="decision_making", confidence=0.3, created_at=now - timedelta(minutes=3)),
    ]
    res_low = calculate_overreliance(low_conf_history, reference_time=now)
    assert res_low["score"] == 3
    assert res_low["signal"] == "low"

    high_conf_history = [
        PromptRecord(classification="convergent", subtype="decision_making", confidence=1.0, created_at=now - timedelta(minutes=1)),
        PromptRecord(classification="convergent", subtype="decision_making", confidence=1.0, created_at=now - timedelta(minutes=2)),
        PromptRecord(classification="convergent", subtype="decision_making", confidence=1.0, created_at=now - timedelta(minutes=3)),
    ]
    res_high = calculate_overreliance(high_conf_history, reference_time=now)
    assert res_high["score"] == 9
    assert res_high["signal"] == "high"


def test_cache_ttl_expiration():
    from app.classifier import CLASSIFIER_CACHE, classify_prompt
    import app.classifier as classifier_mod
    CLASSIFIER_CACHE.clear()

    test_prompt = "What is 100 * 200?"
    res1 = classify_prompt(test_prompt)

    model = os.getenv("CLASSIFIER_MODEL", "gpt-4o-mini")
    import hashlib
    h = hashlib.sha256(test_prompt.strip().lower().encode("utf-8")).hexdigest()
    cache_key = f"v{classifier_mod.CLASSIFIER_VERSION}:{model}:{h}"

    assert cache_key in CLASSIFIER_CACHE
    stored_time, stored_res = CLASSIFIER_CACHE[cache_key]
    CLASSIFIER_CACHE[cache_key] = (stored_time - 90000, stored_res)

    res2 = classify_prompt(test_prompt)
    assert res2.classification == res1.classification
    new_time, _ = CLASSIFIER_CACHE[cache_key]
    assert new_time > stored_time


def test_classifier_true_lru_cache_eviction(monkeypatch):
    import app.classifier as classifier_mod
    from app.classifier import CLASSIFIER_CACHE, classify_prompt
    import hashlib

    CLASSIFIER_CACHE.clear()
    monkeypatch.setattr(classifier_mod, "MAX_CACHE_SIZE", 2)

    prompt_a = "Prompt A for LRU test"
    prompt_b = "Prompt B for LRU test"
    prompt_c = "Prompt C for LRU test"

    def get_key(p):
        h = hashlib.sha256(p.strip().lower().encode("utf-8")).hexdigest()
        return f"v{classifier_mod.CLASSIFIER_VERSION}:{os.getenv('CLASSIFIER_MODEL', 'gpt-4o-mini')}:{h}"

    key_a = get_key(prompt_a)
    key_b = get_key(prompt_b)
    key_c = get_key(prompt_c)

    classify_prompt(prompt_a)
    classify_prompt(prompt_b)
    assert list(CLASSIFIER_CACHE.keys()) == [key_a, key_b]

    classify_prompt(prompt_a)
    assert list(CLASSIFIER_CACHE.keys()) == [key_b, key_a]

    classify_prompt(prompt_c)
    assert key_b not in CLASSIFIER_CACHE
    assert key_a in CLASSIFIER_CACHE
    assert key_c in CLASSIFIER_CACHE
    assert list(CLASSIFIER_CACHE.keys()) == [key_a, key_c]

