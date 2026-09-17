from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.llm.xai_provider import XAIProvider
from backend.llm.base import BaseLLMProvider
from backend.query_engine.executor import QueryExecutor
from backend.core.logging import logger

router = APIRouter(tags=["Natural Language Query Engine"])


class NaturalLanguageQueryRequest(BaseModel):
    """User input question payload."""
    question: str = Field(..., min_length=2, max_length=1000, description="Natural language support analytics question")


class NaturalLanguageQueryResponse(BaseModel):
    """Structured, factual analytics response."""
    question: str
    interpretation: Dict[str, Any]
    answer: str
    data: List[Dict[str, Any]]
    metadata: Dict[str, Any]


def get_llm_provider() -> BaseLLMProvider:
    """Dependency provider for the LLM intent translation engine."""
    return XAIProvider()


@router.post(
    "/query",
    response_model=NaturalLanguageQueryResponse,
    summary="Process Natural Language Support Analytics Query",
    description=(
        "Translates natural language questions into strict structured intent representations via LLM, "
        "validates against allowlists, and deterministically executes parameterized queries against SQLite."
    )
)
async def process_natural_language_query(
    payload: NaturalLanguageQueryRequest,
    db: Session = Depends(get_db),
    llm: BaseLLMProvider = Depends(get_llm_provider)
):
    """
    End-to-end Natural Language Query Pipeline:
    1. Receive user prompt.
    2. LLM translates prompt to strict StructuredIntent AST.
    3. Python validator enforces allowlists and boundaries.
    4. QueryExecutor runs safe parameterized SQLite queries.
    5. Returns grounded, 100% factual result.
    """
    question = payload.question.strip()
    logger.info(f"Received NL Query: '{question}'")

    # Step 1: LLM Intent Translation
    intent = await llm.generate_intent(question)
    
    # Step 2: Deterministic Python Execution against Database
    executor = QueryExecutor(db)
    result = executor.execute(intent)

    return result
