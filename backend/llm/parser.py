import json
import re
from typing import Dict, Any, Optional
from pydantic import ValidationError

from backend.query_engine.intent_schema import StructuredIntent, QueryIntentType
from backend.core.logging import logger
from backend.core.exceptions import AppException


class LLMParseError(AppException):
    """Raised when LLM output cannot be parsed into a StructuredIntent."""
    def __init__(self, message: str, raw_output: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=422,
            details={"raw_output": raw_output[:500], **(details or {})}
        )


def clean_json_text(text: str) -> str:
    """Extract and sanitize JSON from model response."""
    text = text.strip()
    
    # 1. Match code block ```json ... ``` or ``` ... ```
    code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if code_block_match:
        text = code_block_match.group(1).strip()

    # 2. Extract outermost curly braces if extra text surrounds JSON
    brace_match = re.search(r"(\{[\s\S]*\})", text)
    if brace_match:
        text = brace_match.group(1).strip()

    return text


def parse_intent_response(raw_text: str, question: str) -> StructuredIntent:
    """Parse and validate LLM output into a Pydantic StructuredIntent."""
    cleaned = clean_json_text(raw_text)
    
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode LLM JSON: {e} | Raw text: {raw_text[:200]}")
        raise LLMParseError(f"Malformed JSON from LLM: {str(e)}", raw_output=raw_text)

    if not isinstance(data, dict):
        raise LLMParseError("LLM response is not a JSON object", raw_output=raw_text)

    # Ensure raw_question is populated
    if not data.get("raw_question"):
        data["raw_question"] = question

    try:
        return StructuredIntent.model_validate(data)
    except ValidationError as e:
        logger.error(f"Pydantic validation failed on LLM intent output: {e}")
        raise LLMParseError(
            f"LLM output violated intent schema: {str(e)}",
            raw_output=raw_text,
            details={"validation_errors": e.errors()}
        )
