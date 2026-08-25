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

CLASSIFIER_VERSION = "2.0.0"
CACHE_TTL_SECONDS = 86400
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
    p = prompt.strip().lower()
    
    factual_patterns = [
        (r"\bwho (?:composed|sculpted|directed|choreographed|engineered|designed|wrote|painted|discovered|developed|created|invented|signed|built|said|conquered|ruled|won|founded|authored)\b", 3.5),
        (r"\bwho (?:is|was) (?:the )?(?:author|writer|prime minister|president|creator|inventor|founder|ruler|king|queen|emperor)\b", 3.5),
        (r"\bwho (?:is|was) known as\b", 3.0),
        (r"\bwhat is the (?:history behind|origin of|invention of|chemical symbol|atomic number|atomic weight|freezing point|boiling point|melting point|speed of|height of|lifespan of|average height|escape velocity|carrying capacity|focal length|capital of|longest river|largest ocean|tallest mountain|population of|currency of|distance between|definition of|meaning of|first element|formula for|headquarters of)\b", 3.5),
        (r"\b(name|identify|state|specify|define|list) the (?:first|author|writer|speed|chemical|term|base units|location|capital|largest|tallest|shortest|longest|deepest|symbol|element|president|founder)\b", 3.2),
        (r"\bin what year\b|\bwhat year (?:did|was|is)\b", 3.0),
        (r"\bwhere (?:is|are) (?:the )?(?:headquarters|capital|located|situated|eiffel|great barrier|pyramids|statue|tower|city|country|headquarters of)\b", 3.2),
        (r"\bhow (?:many|far|long|much|tall|old|fast|deep) (?:bones|planets|keys|players|colors|stripes|chambers|is|does|are|can|was|were)\b", 3.2),
        (r"\bwhat does [a-z0-9\-]+ stand for\b", 3.0),
        (r"\bwhat (?:is|are) (?:the )?(?:capital|population|currency|height|speed|distance|definition|meaning|symbol|formula|origin|author|longest|largest|tallest|first|history)\b", 2.5),
        (r"\bwhere is\b|\bwho was\b|\bwhen did\b|\bwhen was\b", 2.0)
    ]
    
    computation_patterns = [
        (r"\b(calculate|compute|solve for|solve the system|solve the equation|evaluate the integral|square root of|raised to the|factorial of|determinant of|standard deviation of|perimeter of|volume of|area of|hypotenuse of)\b", 3.5),
        (r"\b(compound interest|discount|percent of|percentage of|median of|average of|derivative of|sum of|product of)\b", 3.0),
        (r"\b(?:convert|temperature in)\s+\d+(?:\.\d+)?\s*(?:degrees\s+)?(?:fahrenheit|celsius|kelvin)\b", 3.5),
        (r"\bhow many (?:seconds|minutes|hours|days|weeks|months|years|cents|dollars|grams|meters|inches|feet) (?:are|in)\b", 3.5),
        (r"\b(divide|multiply|add|subtract)\s+\d+\s+(?:by|and|to|from)\b", 3.2),
        (r"\b\d+\s*(?:[\+\-\*\/=\^]|divided by|multiplied by|plus|minus|times)\s*\d+\b", 3.0),
        (r"\b\d+%\s+of\s+\d+\b", 3.0),
        (r"\b\d+\s*[\+\-\*\/]\s*\d+\b", 2.5),
        (r"\b(equation|integral|hypotenuse|determinant|matrix|standard deviation|factorial|median|formula)\b", 1.8)
    ]
    
    code_patterns = [
        (r"\b(typeerror|nullpointerexception|indexerror|keyerror|recursionerror|valueerror|syntaxerror|nameerror|operationalerror|runtimeerror)\b", 3.8),
        (r"\b(traceback|stacktrace|re-render loop|memory leak|infinite loop|infinite while loop|exit with code \d+|segmentation fault|cannot read property|is undefined|out of range)\b", 3.8),
        (r"\b(?:use|write|choose|create)\s+(?:a\s+)?(?:for loop|while loop|recursive function|for\s+loop|while\s+loop|function|class|method)\s+or\s+(?:a\s+)?(?:for loop|while loop|recursive function|for\s+loop|while\s+loop|function|class|method)\b", 4.5),
        (r"\b(?:use|write|choose)\s+(?:a\s+)?(?:for loop|while loop|recursive function|for\s+loop|while\s+loop)\b", 4.2),
        (r"\b(fix this|debug this|fix the|debug why|how do i fix|why does my|why is my|resolve)\s+(?:python|javascript|typescript|rust|sql|react|docker|fastapi|code|function|compiler|query|error|bug|layout|hook|promise|event|regex|regular expression)\b", 3.5),
        (r"\b(def\s+\w+\s*\(|const\s+\w+\s*=|let\s+\w+\s*=|function\s+\w+\s*\(|import\s+\w+|SELECT\s+.+\s+FROM\b|async\/await|useeffect|sqlalchemy|css flexbox)\b", 3.2),
        (r"\b(nullpointer|index out of range|recursion depth|merge conflict|package-lock\.json|cors policy|422 unprocessable|mutable borrow|unhandled promise)\b", 3.2),
        (r"\b(compiler|syntax|debugging|compile|docker container|graphql|endpoint|database table)\b", 2.0)
    ]
    
    decision_patterns = [
        (r"\bshould i (?:accept|buy|sell|lease|adopt|invest|pursue|choose|move|take|switch|sign|rent|stay|upgrade|learn|attend|hire|write|use)\b", 3.8),
        (r"\bhelp me (?:choose|decide) between\b|\bdecide between\b|\bchoose between\b|\bdecide whether\b|\bhelp me choose\b|\bhelp me decide\b", 3.8),
        (r"\bis [a-z0-9]+ or [a-z0-9]+ better for\b|\bis it better to\b|\bweigh the pros and cons\b|\bpros and cons of\b|\bwhich career path\b|\bis it worth upgrading\b|\bevaluate whether\b", 3.5),
        (r"\b(career option|career path|pros and cons|mortgage|degree|savings|freelance|scholarship|hybrid car|electric vehicle)\b", 2.2)
    ]
    
    divergent_patterns = [
        (r"\bwrite a (?:funny |humorous |creative |short |long |lyrical )?(?:poem|story|song|screenplay|essay|verse|backstory)\b", 4.5),
        (r"\b(brainstorm|write an imaginative|draft a whimsical|draft an engaging|draft a creative|suggest creative|imagine what|imagine a world|speculative fiction)\b", 3.8),
        (r"\b(screenplay outline|creative backstory|unconventional ways|innovative ways|alternative uses|novel game mechanics|art concepts|story hooks|marketing campaign ideas|mission statement ideas|design metaphors)\b", 3.8),
        (r"\bsuggest (?:some|\d+)? (?:unique|creative|ideas|themes|concepts|activities|hooks|metaphors)\b", 3.2),
        (r"\bgenerate (?:some|\d+)? (?:themes|ideas|distinct|novel|inspiring|mission)\b", 3.2),
        (r"\b(creative|whimsical|imaginative|speculative|metaphor|lyrical|poem|story|brainstorm|icebreaker)\b", 2.2)
    ]
    
    other_patterns = [
        (r"\b(format this|sort this|convert this|extract all|translate this|remove all duplicate|capitalize the|normalize these|rearrange these|summarize this|strip html|compress this|clean up the|replace all occurrences|turn off notifications)\b", 3.2),
        (r"\b(convert 24-hour|convert \d+-hour|parts of speech|extract the domain|filter this list|parse this log)\b", 3.0),
        (r"\b(format|sort|translate|summarize|convert|extract|lowercase|uppercase|trim|clean)\b", 1.8)
    ]
    
    scores = {
        "factual_lookup": sum(weight for pat, weight in factual_patterns if re.search(pat, p)),
        "computation": sum(weight for pat, weight in computation_patterns if re.search(pat, p)),
        "code_debugging": sum(weight for pat, weight in code_patterns if re.search(pat, p)),
        "decision_making": sum(weight for pat, weight in decision_patterns if re.search(pat, p)),
        "divergent": sum(weight for pat, weight in divergent_patterns if re.search(pat, p)),
        "other": sum(weight for pat, weight in other_patterns if re.search(pat, p))
    }
    
    sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_cat, top_score = sorted_scores[0]
    second_cat, second_score = sorted_scores[1]
    
    margin = top_score - second_score
    
    if top_score == 0.0:
        if "?" in p:
            classification = "convergent"
            subtype = "other"
            confidence = 0.55
            reasoning = "Defaulted to convergent (other) due to presence of question punctuation without distinct domain cues."
        else:
            classification = "convergent"
            subtype = "other"
            confidence = 0.50
            reasoning = "Defaulted to convergent (other) due to lack of distinct divergent or convergent cues."
    elif top_cat == "divergent":
        classification = "divergent"
        subtype = "originality"
        confidence = min(0.98, max(0.65, 0.70 + 0.05 * top_score + 0.05 * margin))
        reasoning = "Classified as divergent due to strong creative generation, ideation, or open-ended phrasing."
    else:
        classification = "convergent"
        subtype = top_cat
        confidence = min(0.98, max(0.65, 0.70 + 0.05 * top_score + 0.05 * margin))
        if top_cat == "factual_lookup":
            reasoning = "Classified as factual lookup based on specific entity, definition, or verifiable reference query cues."
        elif top_cat == "computation":
            reasoning = "Classified as computation based on numerical calculations, math formulas, or equation expressions."
        elif top_cat == "code_debugging":
            reasoning = "Classified as code debugging due to programming syntax, runtime exception, or bug resolution cues."
        elif top_cat == "decision_making":
            reasoning = "Classified as decision-making based on evaluation of personal choices, tradeoffs, or options."
        else:
            reasoning = "Classified as convergent utility task based on structured text transformation or data processing cues."

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
    normalized = prompt.strip().lower()
    prompt_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    model = os.getenv("CLASSIFIER_MODEL", "gpt-4o-mini")
    cache_key = f"v{CLASSIFIER_VERSION}:{model}:{prompt_hash}"
    
    if cache_key in CLASSIFIER_CACHE:
        cached_time, cached_result = CLASSIFIER_CACHE[cache_key]
        if time.time() - cached_time < CACHE_TTL_SECONDS:
            logger.info(f"In-memory cache hit: '{normalized}'")
            return cached_result
        else:
            del CLASSIFIER_CACHE[cache_key]

    try:
        from . import session_store
        import json
        cached_record = session_store.get_cached_prompt_record(
            prompt,
            classifier_version=CLASSIFIER_VERSION,
            max_age_seconds=CACHE_TTL_SECONDS
        )
        if cached_record:
            logger.info(f"Database cache hit: '{normalized}'")
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
            CLASSIFIER_CACHE[cache_key] = (time.time(), result)
            if len(CLASSIFIER_CACHE) > MAX_CACHE_SIZE:
                CLASSIFIER_CACHE.pop(next(iter(CLASSIFIER_CACHE)))
            return result
    except Exception as e:
        logger.warning(f"Database cache lookup failed: {e}")

    api_key = os.getenv("LLM_API_KEY")
    if not api_key or api_key.strip() == "" or api_key.startswith("your-") or api_key == "placeholder":
        logger.info("LLM_API_KEY is not set or contains placeholders. Falling back to local heuristic classifier.")
        heuristic_res = classify_heuristically(prompt)
        CLASSIFIER_CACHE[cache_key] = (time.time(), heuristic_res)
        if len(CLASSIFIER_CACHE) > MAX_CACHE_SIZE:
            CLASSIFIER_CACHE.pop(next(iter(CLASSIFIER_CACHE)))
        return heuristic_res

    base_url = os.getenv("LLM_BASE_URL")

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
                    
                    CLASSIFIER_CACHE[cache_key] = (time.time(), parsed)
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
                
                CLASSIFIER_CACHE[cache_key] = (time.time(), parsed)
                if len(CLASSIFIER_CACHE) > MAX_CACHE_SIZE:
                    CLASSIFIER_CACHE.pop(next(iter(CLASSIFIER_CACHE)))
                    
                return parsed
        except Exception as e:
            logger.warning(f"LLM classification attempt {attempt + 1} failed: {e}")
            last_error = e
            
    raise ValueError(f"LLM classification failed after retrying. Error: {last_error}")

