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

class StructuredExplanation(BaseModel):
    given_inputs: list[str] = Field(
        description="List of inputs explicitly provided in the prompt."
    )
    expected_outputs: list[str] = Field(
        description="List of expected outputs or types of output requested."
    )
    creative_freedom_score: float = Field(
        description="Creative freedom score between 0.0 (strictly defined) and 1.0 (highly open-ended)."
    )
    factual_dependency: Literal["low", "medium", "high"] = Field(
        description="Factual dependency level of the query."
    )
    complexity: Literal["low", "medium", "high"] = Field(
        description="Cognitive complexity of the query."
    )

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
    explanation_details: Optional[StructuredExplanation] = Field(
        default=None,
        description="Structured explanation details containing inputs, outputs, creative freedom, factual dependency, and complexity."
    )
    reflection_prompt: Optional[str] = Field(
        default=None,
        description="Tailored, mindful reflection prompt for convergent prompts. Null for divergent prompts."
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
        r"\bshould i\b",
        r"\bdecide between\b",
        r"\bis it better to\b",
        r"\bchoose between\b",
        r"\bcareer option\b",
        r"\bcareer path\b",
        r"\bhelp me choose\b",
        r"\bwhether to\b",
        r"\bpros and cons of\b"
    ]

    comp_keywords = [
        r"\bsolve\b",
        r"\bcalculate\b",
        r"\bcompute\b",
        r"\bformula\b",
        r"\bequation\b",
        r"\bsum\b",
        r"\baverage\b",
        r"\bmean\b",
        r"\bmedian\b",
        r"\bpercentage\b",
        r"[\+\-\*\/=\^]"
    ]

    factual_keywords = [
        r"\bwhat is the capital\b",
        r"\bwhere is\b",
        r"\bwho was\b",
        r"\bwhen did\b",
        r"\bhow many people\b",
        r"\bheight of\b",
        r"\bdistance between\b",
        r"\bdefinition of\b",
        r"\bwho is\b",
        r"\bwhat does\b",
        r"\bhow old is\b",
        r"\bwhen was\b",
        r"\bwho (?:wrote|painted|discovered|developed|created|invented|designed|signed|built|said|conquered|ruled|won|founded|author of)\b",
        r"\bwho is the author of\b",
        r"\bwho is known as\b",
        r"\bwhat is the (?:chemical|atomic|speed|largest|tallest|longest|deepest|smallest|biggest|boiling|melting|population|currency|capital|height|distance|definition|meaning|formula|symbol|deep ocean zone)\b",
        r"\bin what year\b",
        r"\bwhat year (?:did|was|is)\b",
        r"\bhow many\b",
        r"\bhow (?:far|long|much|tall|old|fast|many)\b"
    ]

    divergent_keywords = [
        r"\bwrite a\b",
        r"\bwrite an\b",
        r"\bwrite some\b",
        r"\bpoem\b",
        r"\bstory\b",
        r"\bsong\b",
        r"\bessay\b",
        r"\bemail\b",
        r"\bdraft\b",
        r"\bcreative\b",
        r"\bimagine\b",
        r"\bdesign a\b",
        r"\bbrainstorm\b",
        r"\bsuggest some\b",
        r"\bideas for\b",
        r"\bwhat are some ways\b",
        r"\bhow can i improve\b",
        r"\bopinions on\b",
        r"\bwhat do you think\b",
        r"\boutline a\b",
        r"\bgenerate\b"
    ]

    imperative_convergent_keywords = [
        r"\bidentify\b",
        r"\bdefine\b",
        r"\bstate the\b",
        r"\bname the\b",
        r"\blist the\b"
    ]

    if any(re.search(pat, p) for pat in code_keywords):
        classification = "convergent"
        confidence = 0.85
        subtype = "code_debugging"
        reasoning = "Classified heuristically as code debugging due to code syntactical structures or programming keywords."
    elif any(re.search(pat, p) for pat in decision_keywords):
        classification = "convergent"
        confidence = 0.80
        subtype = "decision_making"
        reasoning = "Classified heuristically as a decision-making task involving evaluating choices or weighing personal outcomes."
    elif any(re.search(pat, p) for pat in comp_keywords) and any(char.isdigit() for char in p):
        classification = "convergent"
        confidence = 0.90
        subtype = "computation"
        reasoning = "Classified heuristically as computation based on numerical values and math keywords/symbols."
    elif any(re.search(pat, p) for pat in factual_keywords):
        classification = "convergent"
        confidence = 0.85
        subtype = "factual_lookup"
        reasoning = "Classified heuristically as a factual lookup based on factual query keywords."
    elif any(re.search(pat, p) for pat in divergent_keywords):
        classification = "divergent"
        confidence = 0.85
        subtype = "originality"
        reasoning = "Classified heuristically as divergent/open-ended due to content creation or brainstorming keywords."
    elif any(re.search(pat, p) for pat in imperative_convergent_keywords):
        classification = "convergent"
        confidence = 0.70
        subtype = "other"
        reasoning = "Classified heuristically as convergent (other) due to imperative command keywords."
    elif "?" in p:
        classification = "convergent"
        confidence = 0.60
        subtype = "other"
        reasoning = "Defaulted to convergent (other) due to presence of a question mark without strong divergent signals."

    # Generate heuristic structured explanation and reflection prompts
    if classification == "convergent":
        if subtype == "code_debugging":
            explanation_details = StructuredExplanation(
                given_inputs=[prompt[:100]],
                expected_outputs=["fixed code/implementation"],
                creative_freedom_score=0.2,
                factual_dependency="low",
                complexity="high"
            )
            reflection_prompt = "What are the main edge cases in this code/algorithm?"
        elif subtype == "decision_making":
            explanation_details = StructuredExplanation(
                given_inputs=[prompt[:100]],
                expected_outputs=["recommended decision/action"],
                creative_freedom_score=0.5,
                factual_dependency="low",
                complexity="high"
            )
            reflection_prompt = "What bias might influence this decision, and how can you counter it?"
        elif subtype == "computation":
            explanation_details = StructuredExplanation(
                given_inputs=[prompt[:100]],
                expected_outputs=["mathematical/numerical solution"],
                creative_freedom_score=0.0,
                factual_dependency="low",
                complexity="medium"
            )
            reflection_prompt = "Have you double-checked the mathematical logic or syntax?"
        elif subtype == "factual_lookup":
            explanation_details = StructuredExplanation(
                given_inputs=[prompt[:100]],
                expected_outputs=["factual query resolution"],
                creative_freedom_score=0.1,
                factual_dependency="high",
                complexity="low"
            )
            reflection_prompt = "How will you verify this factual claim independently?"
        else:
            explanation_details = StructuredExplanation(
                given_inputs=[prompt[:100]],
                expected_outputs=["specific answer/response"],
                creative_freedom_score=0.3,
                factual_dependency="medium",
                complexity="medium"
            )
            reflection_prompt = "Are there any alternative parameters we should consider?"
    else:
        explanation_details = StructuredExplanation(
            given_inputs=[prompt[:100]],
            expected_outputs=["creative ideas/options"],
            creative_freedom_score=0.9,
            factual_dependency="low",
            complexity="medium"
        )
        reflection_prompt = None

    return PromptClassificationResult(
        classification=classification,
        confidence=confidence,
        subtype=subtype,
        reasoning=reasoning,
        explanation_details=explanation_details,
        reflection_prompt=reflection_prompt,
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
                explanation_details=explanation_details,
                reflection_prompt=cached_record.reflection_prompt,
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


    api_key = os.getenv("LLM_API_KEY")
    if not api_key or api_key.strip() == "" or api_key.startswith("your-") or api_key == "placeholder":
        logger.info("LLM_API_KEY is not set or contains placeholders. Falling back to local heuristic classifier.")
        return classify_heuristically(prompt)

    base_url = os.getenv("LLM_BASE_URL")
    model = os.getenv("CLASSIFIER_MODEL", "gpt-4o-mini")

    client_args = {"api_key": api_key}
    if base_url:
        client_args["base_url"] = base_url
    client = OpenAI(**client_args)
    
    last_error = None
    system_prompt = (
        "You are a prompt classifier that categorizes prompts according to J.P. Guilford's convergent/divergent theory.\n"
        "Convergent: tasks with a single, verifiable, correct answer (e.g. math, factual lookups, debugging, choice decisions).\n"
        "For convergent prompts, choose one of these subtypes: 'factual_lookup', 'computation', 'code_debugging', 'decision_making', 'other'.\n"
        "For convergent prompts, you MUST generate a tailored, mindful 'reflection_prompt' to encourage user critical thinking before relying on the AI (e.g., 'What are the main edge cases in this algorithm?', 'How will you verify this factual claim independently?', 'Are there any alternative parameters we should consider?').\n"
        "Divergent: open-ended tasks generating multiple options/possibilities (e.g. brainstorming, writing, creative design).\n"
        "For divergent prompts, choose one of Guilford's creative domains as the subtype: 'fluency' (speed/quantity of ideas), 'flexibility' (different categories/perspectives), 'originality' (unique/unusual ideas), 'elaboration' (building/expanding on ideas). For divergent prompts, reflection_prompt MUST be null.\n"
        "For all prompts, populate the 'explanation_details' object matching the StructuredExplanation schema:\n"
        "  - given_inputs: list of strings (explicit inputs provided in user prompt)\n"
        "  - expected_outputs: list of strings (expected outputs/targets)\n"
        "  - creative_freedom_score: float between 0.0 (strictly defined) and 1.0 (highly open-ended)\n"
        "  - factual_dependency: 'low' | 'medium' | 'high'\n"
        "  - complexity: 'low' | 'medium' | 'high'\n"
        "Provide the classification, a confidence score between 0.0 and 1.0, a single-sentence reasoning, the subtype, explanation_details, and reflection_prompt.\n"
        "You MUST return your output as a valid JSON object matching the PromptClassificationResult schema."
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
                    if parsed.classification == "divergent" and parsed.subtype not in ["fluency", "flexibility", "originality", "elaboration"]:
                        parsed.subtype = None
                    elif parsed.classification == "convergent" and parsed.subtype not in ["factual_lookup", "computation", "code_debugging", "decision_making", "other"]:
                        parsed.subtype = "other"
                    
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
                if parsed.classification == "divergent" and parsed.subtype not in ["fluency", "flexibility", "originality", "elaboration"]:
                    parsed.subtype = None
                elif parsed.classification == "convergent" and parsed.subtype not in ["factual_lookup", "computation", "code_debugging", "decision_making", "other"]:
                    parsed.subtype = "other"
                
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
