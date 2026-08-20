import os
import time
import hashlib
import re
import logging
from typing import Literal, Optional
from pydantic import BaseModel, Field
from openai import OpenAI

logger = logging.getLogger("prompt_classifier")
logging.basicConfig(level=logging.INFO)

CONFIDENCE_THRESHOLD = 0.6

CLASSIFIER_CACHE = {}
MAX_CACHE_SIZE = 500

class PromptClassificationResult(BaseModel):
    classification: Literal["convergent", "divergent"] = Field(
        description="Whether the prompt is convergent (narrows to a single correct/verifiable answer) or divergent (open-ended/multiple valid possibilities)."
    )
    confidence: float = Field(
        description="Confidence score for this classification, between 0.0 and 1.0."
    )
    reasoning: str = Field(
        description="A single-sentence explanation for the classification and chosen subtype."
    )
    subtype: Optional[Literal["factual_lookup", "computation", "code_debugging", "decision_making", "other", "fluency", "flexibility", "originality", "elaboration"]] = Field(
        default=None,
        description="Subtype for convergent prompts or divergent Guilford's creative domains."
    )
    latency_ms: Optional[int] = Field(
        default=None,
        description="Latency in milliseconds for the LLM call."
    )
    total_tokens: Optional[int] = Field(
        default=None,
        description="Total tokens consumed by the LLM call."
    )

def classify_heuristically(prompt: str) -> PromptClassificationResult:
    """
    Local heuristic/regex-based classifier that executes out-of-the-box
    without requiring an OpenAI API key.
    """
    p = prompt.strip().lower()
    
    classification = "convergent"
    confidence = 0.60
    subtype = "other"
    reasoning = "Defaulted to convergent (other) due to lack of strong divergent signals."

    code_keywords = [
        r"\bdef\s+\w+\b",
        r"\bclass\s+\w+\b",
        r"\bfunction\b",
        r"\bconst\b",
        r"\blet\b",
        r"\bimport\b",
        r"\berror\b",
        r"\bbug\b",
        r"\bexception\b",
        r"\btraceback\b",
        r"\bcompile\b",
        r"\bjavascript\b",
        r"\bpython\b",
        r"\btypescript\b",
        r"\breact\b",
        r"\bcss\b",
        r"\bfix this\b",
        r"\{\s*\"",
        r"\bloop\b",
        r"\bfor\s+loop\b",
        r"\bwhile\b"
    ]
    
    decision_keywords = [
        r"\bchoose\b",
        r"\bdecide\b",
        r"\bdecision\b",
        r"\boption\b",
        r"\bshould i\b",
        r"\bwould you recommend\b",
        r"\bcomparison\b",
        r"\bcompare\b"
    ]
    
    comp_keywords = [
        r"\bcalculate\b",
        r"\bcompute\b",
        r"\bsolve\b",
        r"\badd\b",
        r"\bsubtract\b",
        r"\bmultiply\b",
        r"\bdivide\b",
        r"\bsum\b",
        r"\bproduct\b",
        r"\bmath\b",
        r"\bformula\b",
        r"\bpercent\b",
        r"\baverage\b",
        r"\bmean\b",
        r"\bmedian\b",
        r"\bmode\b",
        r"\bstd\s*dev\b"
    ]
    
    factual_keywords = [
        r"\bwhat is\b",
        r"\bwho is\b",
        r"\bwhen did\b",
        r"\bwhere is\b",
        r"\bhow many\b",
        r"\bdefine\b",
        r"\blist\b",
        r"\bhistory\b",
        r"\bcapital of\b",
        r"\bpopulation of\b"
    ]
    
    divergent_keywords = [
        r"\bwrite\b",
        r"\bcreate\b",
        r"\bgenerate\b",
        r"\bdesign\b",
        r"\bcompose\b",
        r"\bdraft\b",
        r"\bbrainstorm\b",
        r"\bideas\b",
        r"\bsuggest\b",
        r"\binvent\b"
    ]
    
    imperative_convergent_keywords = [
        r"\bfind\b",
        r"\bget\b",
        r"\bsearch\b",
        r"\brun\b",
        r"\bexecute\b"
    ]

    # Check heuristic ordering: Code debugging first, then Decision making, then Computation, Factual lookup, Divergent, Imperative
    if any(re.search(pat, p) for pat in code_keywords):
        subtype = "code_debugging"
        reasoning = "Classified heuristically as code debugging due to code syntactical structures or programming keywords."
    elif any(re.search(pat, p) for pat in decision_keywords):
        subtype = "decision_making"
        reasoning = "Classified heuristically as decision-making based on decision/choice keywords."
    elif any(re.search(pat, p) for pat in comp_keywords) and any(char.isdigit() for char in p):
        subtype = "computation"
        reasoning = "Classified heuristically as computation based on numerical values and math keywords/symbols."
    elif any(re.search(pat, p) for pat in factual_keywords):
        subtype = "factual_lookup"
        reasoning = "Classified heuristically as a factual lookup based on factual query keywords."
    elif any(re.search(pat, p) for pat in divergent_keywords):
        classification = "divergent"
        subtype = None
        reasoning = "Classified heuristically as divergent/open-ended due to content creation or brainstorming keywords."
    elif any(re.search(pat, p) for pat in imperative_convergent_keywords):
        subtype = "other"
        reasoning = "Classified heuristically as convergent (other) due to imperative command keywords."

    return PromptClassificationResult(
        classification=classification,
        confidence=confidence,
        subtype=subtype,
        reasoning=reasoning,
        latency_ms=0,
        total_tokens=0
    )

def _extract_tokens(response) -> Optional[int]:
    raw_tokens = getattr(getattr(response, "usage", None), "total_tokens", None)
    if raw_tokens is None:
        return None
    if isinstance(raw_tokens, int):
        return raw_tokens
    try:
        return int(raw_tokens)
    except (TypeError, ValueError):
        return None

def classify_prompt(prompt: str) -> PromptClassificationResult:
    """
    Main entry point for prompt classification. Checks for LLM_API_KEY in environment.
    Connects to LLM_BASE_URL (supporting any OpenAI-API-compatible provider) and uses CLASSIFIER_MODEL.
    """
    normalized = prompt.strip().lower()
    prompt_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    if prompt_hash in CLASSIFIER_CACHE:
        logger.info(f"Cache hit for prompt classification: '{normalized}'")
        return CLASSIFIER_CACHE[prompt_hash]

    # Check database-backed persistent cache
    try:
        from . import session_store
        import json
        cached_record = session_store.get_cached_prompt_record(prompt)
        if cached_record:
            logger.info(f"Database cache hit for prompt classification: '{normalized}'")
            explanation_details = None
            if cached_record.explanation_details:
                try:
                    explanation_details = StructuredExplanation(**json.loads(cached_record.explanation_details))
                except Exception as e:
                    logger.warning(f"Failed to parse explanation_details from cache: {e}")
            
            result = PromptClassificationResult(
                classification=cached_record.classification,
                confidence=cached_record.confidence,
                subtype=cached_record.subtype,
                reasoning=cached_record.reasoning,

                latency_ms=0,
                total_tokens=0
            )
            # Store in in-memory cache
            CLASSIFIER_CACHE[prompt_hash] = result
            if len(CLASSIFIER_CACHE) > MAX_CACHE_SIZE:
                CLASSIFIER_CACHE.pop(next(iter(CLASSIFIER_CACHE)))
            return result
    except Exception as e:
        logger.warning(f"Database cache lookup failed: {e}")


    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.strip() == "" or api_key.startswith("your-") or api_key == "placeholder":
        logger.info("OPENAI_API_KEY is not set or contains placeholders. Falling back to local heuristic classifier.")
        return classify_heuristically(prompt)

    base_url = os.getenv("OPENAI_BASE_URL")
    model = os.getenv("CLASSIFIER_MODEL", "gpt-4o-mini")

    client_args = {"api_key": api_key}
    if base_url:
        client_args["base_url"] = base_url
    client = OpenAI(**client_args)
    
    last_error = None
    system_prompt = (
        "You are a prompt classifier that categorizes prompts according to J.P. Guilford's convergent/divergent theory.\n"
        "Convergent: tasks with a single, verifiable, correct answer (e.g. math, factual lookups, debugging, choice decisions).\n"
"Provide the classification, a confidence score between 0.0 and 1.0, a single-sentence reasoning, and if convergent, a subtype ('factual_lookup', 'computation', 'code_debugging', 'decision_making', 'other').\n"
        "If the prompt is divergent, the subtype MUST be null.\n"
        "You MUST return your output as a valid JSON object matching this schema:\n"
        "{\n"
        '  "classification": "convergent" | "divergent",\n'
        '  "confidence": float,\n'
        '  "reasoning": "string",\n'
        '  "subtype": "factual_lookup" | "computation" | "code_debugging" | "decision_making" | "other" | null\n'
        "}"
    )

    for attempt in range(2):
        try:
            is_openai_official = not base_url or "api.openai.com" in base_url
            
            if is_openai_official and model.startswith("gpt-"):
                start_time = time.perf_counter()
                response = client.beta.chat.completions.parse(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    response_format=PromptClassificationResult
                )
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                parsed = response.choices[0].message.parsed
                if parsed:
                    if parsed.classification == "divergent":
                        parsed.subtype = None
                    
                    if parsed.confidence < CONFIDENCE_THRESHOLD:
                        logger.warning(f"LLM confidence {parsed.confidence} below threshold {CONFIDENCE_THRESHOLD}. Falling back to heuristic classifier.")
                        heuristic_res = classify_heuristically(prompt)
                        heuristic_res.reasoning = f"{heuristic_res.reasoning} (LLM confidence below threshold, using heuristic fallback)"
                        return heuristic_res
                    
                    parsed.latency_ms = latency_ms
                    parsed.total_tokens = _extract_tokens(response)
                    
                    # Cache successful result
                    CLASSIFIER_CACHE[prompt_hash] = parsed
                    if len(CLASSIFIER_CACHE) > MAX_CACHE_SIZE:
                        CLASSIFIER_CACHE.pop(next(iter(CLASSIFIER_CACHE)))
                        
                    return parsed
                else:
                    raise ValueError("Parsed response is None")
            else:
                start_time = time.perf_counter()
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                content = response.choices[0].message.content
                if not content:
                    raise ValueError("Empty response content from LLM")
                
                import json
                data = json.loads(content)
                parsed = PromptClassificationResult(**data)
                if parsed.classification == "divergent":
                    parsed.subtype = None
                
                if parsed.confidence < CONFIDENCE_THRESHOLD:
                    logger.warning(f"LLM confidence {parsed.confidence} below threshold {CONFIDENCE_THRESHOLD}. Falling back to heuristic classifier.")
                    heuristic_res = classify_heuristically(prompt)
                    heuristic_res.reasoning = f"{heuristic_res.reasoning} (LLM confidence below threshold, using heuristic fallback)"
                    return heuristic_res
                
                parsed.latency_ms = latency_ms
                parsed.total_tokens = _extract_tokens(response)
                
                # Cache successful result
                CLASSIFIER_CACHE[prompt_hash] = parsed
                if len(CLASSIFIER_CACHE) > MAX_CACHE_SIZE:
                    CLASSIFIER_CACHE.pop(next(iter(CLASSIFIER_CACHE)))
                    
                return parsed
        except Exception as e:
            logger.warning(f"LLM classification attempt {attempt + 1} failed: {e}")
            last_error = e
            
    raise ValueError(f"LLM classification failed after retrying. Error: {last_error}")
