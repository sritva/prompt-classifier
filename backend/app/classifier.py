import os
import re
import logging
from typing import Literal, Optional
from pydantic import BaseModel, Field
from openai import OpenAI

logger = logging.getLogger("prompt_classifier")
logging.basicConfig(level=logging.INFO)

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
    subtype: Optional[Literal["factual_lookup", "computation", "code_debugging", "decision_making", "other"]] = Field(
        default=None,
        description="Subtype for convergent prompts. MUST be null for divergent prompts."
    )

def classify_heuristically(prompt: str) -> PromptClassificationResult:
    """
    Local heuristic/regex-based classifier that executes out-of-the-box
    without requiring an OpenAI API key.
    """
    p = prompt.strip().lower()
    
    # 1. Decision Making keywords
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
    if any(re.search(pat, p) for pat in decision_keywords):
        return PromptClassificationResult(
            classification="convergent",
            confidence=0.80,
            subtype="decision_making",
            reasoning="Classified heuristically as a decision-making task involving evaluating choices or weighing personal outcomes."
        )

    # 2. Code Debugging keywords
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
        r"\{\s*\""
    ]
    if any(re.search(pat, p) for pat in code_keywords):
        return PromptClassificationResult(
            classification="convergent",
            confidence=0.85,
            subtype="code_debugging",
            reasoning="Classified heuristically as code debugging due to code syntactical structures or programming keywords."
        )

    # 3. Computation keywords
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
    if any(re.search(pat, p) for pat in comp_keywords) and any(char.isdigit() for char in p):
        return PromptClassificationResult(
            classification="convergent",
            confidence=0.90,
            subtype="computation",
            reasoning="Classified heuristically as computation based on numerical values and math keywords/symbols."
        )

    # 4. Factual Lookup keywords
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
        r"\bwhen was\b"
    ]
    if any(re.search(pat, p) for pat in factual_keywords):
        return PromptClassificationResult(
            classification="convergent",
            confidence=0.85,
            subtype="factual_lookup",
            reasoning="Classified heuristically as a factual lookup based on factual query keywords."
        )

    # 5. Divergent / Open-ended keywords
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
    if any(re.search(pat, p) for pat in divergent_keywords):
        return PromptClassificationResult(
            classification="divergent",
            confidence=0.85,
            subtype=None,
            reasoning="Classified heuristically as divergent/open-ended due to content creation or brainstorming keywords."
        )

    # Default fallback: convergent/other or divergent?
    # Let's say if it contains a question mark, it's convergent (other), else divergent (open-ended statement).
    if "?" in p:
        return PromptClassificationResult(
            classification="convergent",
            confidence=0.60,
            subtype="other",
            reasoning="Defaulted to convergent (other) due to presence of a question mark without strong divergent signals."
        )
    else:
        return PromptClassificationResult(
            classification="divergent",
            confidence=0.60,
            subtype=None,
            reasoning="Defaulted to divergent due to open-ended statement phrasing and lack of convergent signals."
        )

def classify_prompt(prompt: str) -> PromptClassificationResult:
    """
    Main entry point for prompt classification. Checks for OPENAI_API_KEY
    and calls OpenAI GPT-4o-mini with structured outputs. If not configured,
    uses the local regex heuristic.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    # If the key is not set or contains the default template value, use fallback
    if not api_key or api_key.strip() == "" or api_key.startswith("your-") or api_key == "placeholder":
        logger.info("OPENAI_API_KEY is not set or contains placeholders. Falling back to local heuristic classifier.")
        return classify_heuristically(prompt)

    # Call OpenAI with structured output
    client = OpenAI(api_key=api_key)
    
    # Retry logic (up to 1 retry)
    last_error = None
    for attempt in range(2):
        try:
            # We'll use structured outputs format
            response = client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a prompt classifier that categorizes prompts according to J.P. Guilford's convergent/divergent theory.\n"
                            "Convergent: tasks with a single, verifiable, correct answer (e.g. math, factual lookups, debugging, choice decisions).\n"
                            "Divergent: open-ended tasks generating multiple options/possibilities (e.g. brainstorming, writing, creative design).\n"
                            "Provide the classification, a confidence score between 0.0 and 1.0, a single-sentence reasoning, and if convergent, a subtype ('factual_lookup', 'computation', 'code_debugging', 'decision_making', 'other').\n"
                            "If the prompt is divergent, the subtype MUST be null."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format=PromptClassificationResult
            )
            parsed = response.choices[0].message.parsed
            if parsed:
                # Validate that divergent has no subtype
                if parsed.classification == "divergent" and parsed.subtype is not None:
                    parsed.subtype = None
                return parsed
            else:
                raise ValueError("Parsed response is None")
        except Exception as e:
            logger.warning(f"OpenAI classification attempt {attempt + 1} failed: {e}")
            last_error = e
            
    # If both attempts failed, raise a ValueError with the error
    raise ValueError(f"OpenAI classification failed after retrying. Error: {last_error}")
