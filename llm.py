import json
import re
from typing import Dict, Any, List, Optional, Tuple, Literal
import httpx
from pydantic import BaseModel, Field, ValidationError
from app.config import LLM_BASE_URL, LLM_API_KEY, LLM_MODEL

SYSTEM_PROMPT = (
    "You are a privacy-analysis assistant. You compare a user's ORIGINAL consent purpose with "
    "a newly received EVIDENCE text. You must respond with ONLY a valid JSON object, no markdown, "
    "no commentary. Never claim a legal violation. Never claim data was actually shared; only describe "
    "what the evidence says. Every item in evidence_quotes MUST be an exact, verbatim substring of the "
    "EVIDENCE text. If the evidence has no meaningful data-use content, set insufficient_evidence to true."
)

USER_PROMPT_TEMPLATE = """ORIGINAL PURPOSE: {original_purpose}
ORIGINAL DATA CATEGORIES: {categories}
EVIDENCE TYPE: {type}
EVIDENCE: {content}
Return JSON with this exact schema:
{{
  "insufficient_evidence": boolean,
  "original_purposes": [string],
  "new_purposes": [string],
  "data_categories_affected": [string],
  "third_party_sharing": "yes" | "no" | "unclear",
  "covered_by_original_purpose": boolean,
  "additional_purposes_not_covered": [string],
  "evidence_quotes": [string],
  "explanation": string,
  "confidence": number between 0 and 1
}}"""

class LLMResponseSchema(BaseModel):
    insufficient_evidence: bool = False
    original_purposes: List[str] = Field(default_factory=list)
    new_purposes: List[str] = Field(default_factory=list)
    data_categories_affected: List[str] = Field(default_factory=list)
    third_party_sharing: Literal["yes", "no", "unclear"] = "unclear"
    covered_by_original_purpose: bool = True
    additional_purposes_not_covered: List[str] = Field(default_factory=list)
    evidence_quotes: List[str] = Field(default_factory=list)
    explanation: str = ""
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)

def strip_markdown_fences(text: str) -> str:
    """Strip markdown ```json ... ``` or ``` fences if present."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text

def parse_and_validate(raw_text: str) -> Optional[Dict[str, Any]]:
    clean_text = strip_markdown_fences(raw_text)
    try:
        data = json.loads(clean_text)
        validated = LLMResponseSchema.model_validate(data)
        return validated.model_dump()
    except (json.JSONDecodeError, ValidationError):
        return None

def call_chat_completions(messages: List[Dict[str, str]]) -> str:
    url = f"{LLM_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": 0.0,
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

def extract_with_llm(
    original_purpose: str,
    data_categories: List[str],
    evidence_type: str,
    evidence_text: str
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Attempt structured extraction using the configured LLM.
    Returns:
        (llm_data, warning_if_failed_or_skipped)
    """
    if not LLM_API_KEY:
        return None, None

    user_prompt = USER_PROMPT_TEMPLATE.format(
        original_purpose=original_purpose,
        categories=", ".join(data_categories) if data_categories else "None specified",
        type=evidence_type,
        content=evidence_text
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

    try:
        first_reply = call_chat_completions(messages)
        parsed = parse_and_validate(first_reply)
        if parsed is not None:
            return parsed, None

        # Retry once on invalid JSON
        messages.append({"role": "assistant", "content": first_reply})
        messages.append({
            "role": "user",
            "content": "Your last reply was invalid JSON. Reply with only the JSON object."
        })

        second_reply = call_chat_completions(messages)
        parsed_retry = parse_and_validate(second_reply)
        if parsed_retry is not None:
            return parsed_retry, None

        return None, "LLM returned invalid JSON after retry; fell back to rules-only mode."

    except Exception as e:
        return None, f"LLM call failed ({type(e).__name__}); fell back to rules-only mode."
