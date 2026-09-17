import re
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import httpx

from backend.config import settings
from backend.core.logging import logger
from backend.llm.base import BaseLLMProvider
from backend.llm.prompts import SYSTEM_PROMPT
from backend.llm.parser import parse_intent_response, LLMParseError
from backend.query_engine.intent_schema import (
    StructuredIntent,
    QueryIntentType,
    MetricType,
    DimensionType,
    FilterClause,
    FilterOperator,
    DateRangeSpec,
    RelativePeriod,
    SortSpec,
    SortOrder,
)


class RuleBasedFallbackProvider(BaseLLMProvider):
    """
    Zero-Cost Deterministic Semantic Fallback Provider.
    
    Transforms natural language questions into strict StructuredIntent ASTs
    using deterministic grammar and semantic rule-matching.
    Ensures 100% operational readiness at zero cost without requiring API keys.
    """

    async def generate_intent(self, question: str) -> StructuredIntent:
        q = question.lower().strip()
        
        # 1. Detect Anomaly Intent
        if any(w in q for w in ["anomaly", "anomalies", "outlier", "outliers", "unusual", "spike", "irregular"]):
            rel_period = None
            if "this week" in q:
                rel_period = RelativePeriod.THIS_WEEK
            elif "last week" in q:
                rel_period = RelativePeriod.LAST_WEEK
            elif "this month" in q:
                rel_period = RelativePeriod.THIS_MONTH
            elif "last month" in q:
                rel_period = RelativePeriod.LAST_MONTH
                
            return StructuredIntent(
                intent=QueryIntentType.ANOMALY_DETECTION,
                metrics=[MetricType.AVG_RESOLUTION_TIME],
                group_by=[],
                filters=[],
                date_range=DateRangeSpec(relative_period=rel_period) if rel_period else None,
                anomaly_request=True,
                raw_question=question,
                confidence=1.0,
                notes="Rule-based parser: Anomaly detection route"
            )

        # 2. Extract Category Filter
        filters: List[FilterClause] = []
        if "billing" in q:
            filters.append(FilterClause(field="category", operator=FilterOperator.EQ, value="Billing"))
        elif "technical" in q:
            filters.append(FilterClause(field="category", operator=FilterOperator.EQ, value="Technical"))
        elif "general" in q:
            filters.append(FilterClause(field="category", operator=FilterOperator.EQ, value="General"))

        # 3. Extract Priority Filter
        if "critical" in q:
            filters.append(FilterClause(field="priority", operator=FilterOperator.EQ, value="Critical"))
        elif "high" in q and "priority" in q:
            filters.append(FilterClause(field="priority", operator=FilterOperator.EQ, value="High"))
        elif "medium" in q and "priority" in q:
            filters.append(FilterClause(field="priority", operator=FilterOperator.EQ, value="Medium"))
        elif "low" in q and "priority" in q:
            filters.append(FilterClause(field="priority", operator=FilterOperator.EQ, value="Low"))

        # 4. Extract Status & Unresolved Logic
        unresolved_only = False
        if "unresolved" in q or "not resolved" in q or "open" in q or "escalated" in q:
            unresolved_only = True
            if "open" in q and "escalated" not in q and "unresolved" not in q:
                filters.append(FilterClause(field="status", operator=FilterOperator.EQ, value="Open"))
            elif "escalated" in q and "open" not in q:
                filters.append(FilterClause(field="status", operator=FilterOperator.EQ, value="Escalated"))
            elif "unresolved" in q:
                filters.append(FilterClause(field="status", operator=FilterOperator.IN, value=["Open", "Escalated"]))
        elif "resolved" in q:
            filters.append(FilterClause(field="status", operator=FilterOperator.EQ, value="Resolved"))

        # 5. Extract Resolution time threshold (e.g., "not resolved within 12 hours" or "> 12 hours")
        hrs_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours|hrs|hour)", q)
        if hrs_match:
            hrs_val = float(hrs_match.group(1))
            if any(w in q for w in ["not resolved within", "longer than", "more than", "over", ">", "exceeding"]):
                filters.append(FilterClause(field="resolution_time_hrs", operator=FilterOperator.GT, value=hrs_val))
            elif any(w in q for w in ["within", "under", "less than", "<"]):
                filters.append(FilterClause(field="resolution_time_hrs", operator=FilterOperator.LTE, value=hrs_val))

        # 6. Extract Relative or Explicit Date Filter
        date_range = None
        if "this month" in q:
            date_range = DateRangeSpec(relative_period=RelativePeriod.THIS_MONTH)
        elif "last month" in q:
            date_range = DateRangeSpec(relative_period=RelativePeriod.LAST_MONTH)
        elif "this week" in q:
            date_range = DateRangeSpec(relative_period=RelativePeriod.THIS_WEEK)
        elif "last week" in q:
            date_range = DateRangeSpec(relative_period=RelativePeriod.LAST_WEEK)
        elif "today" in q:
            date_range = DateRangeSpec(relative_period=RelativePeriod.TODAY)
        elif "older than 24 hours" in q or "older than 24h" in q:
            date_range = DateRangeSpec(relative_period=RelativePeriod.OLDER_THAN_24H)
        else:
            year_match = re.search(r"\b(19\d\d|20\d\d)\b", q)
            if year_match:
                yr = int(year_match.group(1))
                date_range = DateRangeSpec(
                    start_date=datetime(yr, 1, 1, 0, 0, 0),
                    end_date=datetime(yr, 12, 31, 23, 59, 59)
                )

        # 7. Extract Dimensions (Group By)
        group_by = []
        if any(w in q for w in ["each agent", "by agent", "which agent", "per agent", "who is", "who resolved", "leading agent"]):
            group_by.append(DimensionType.AGENT_ID)
        if "by category" in q or "per category" in q or "each category" in q:
            group_by.append(DimensionType.CATEGORY)
        if "by priority" in q or "per priority" in q:
            group_by.append(DimensionType.PRIORITY)
        if "by status" in q or "per status" in q:
            group_by.append(DimensionType.STATUS)
        if "by month" in q or "monthly" in q:
            group_by.append(DimensionType.MONTH)

        # 8. Extract Metrics
        metrics = []
        if "average customer rating" in q or "average rating" in q or "avg rating" in q:
            metrics.append(MetricType.AVG_RATING)
        elif "average resolution time" in q or "avg resolution" in q:
            metrics.append(MetricType.AVG_RESOLUTION_TIME)
        elif "average response time" in q or "avg response" in q:
            metrics.append(MetricType.AVG_RESPONSE_TIME)
        elif "resolution rate" in q:
            metrics.append(MetricType.RESOLUTION_RATE)
        elif "sla breach" in q or "sla breaches" in q:
            metrics.append(MetricType.SLA_BREACH_COUNT)
        else:
            metrics.append(MetricType.COUNT)

        # 9. Determine Intent Type and Sorting
        sort = None
        limit = 100

        if any(w in q for w in ["which agent", "top agent", "most tickets", "highest", "lowest", "top", "leading", "who resolved", "best"]):
            intent_type = QueryIntentType.TOP_N
            is_asc = any(w in q for w in ["lowest", "least", "worst", "bottom"])
            sort_field = metrics[0].value if metrics else "count"
            sort = SortSpec(field=sort_field, order=SortOrder.ASC if is_asc else SortOrder.DESC)
            limit = 1
            if not group_by:
                group_by.append(DimensionType.AGENT_ID)

        elif group_by and not any(w in q for w in ["show", "list", "find", "get", "display"]):
            intent_type = QueryIntentType.GROUP_BY
            sort = SortSpec(field=metrics[0].value if metrics else "count", order=SortOrder.DESC)

        elif any(w in q for w in ["show", "list", "get all", "find all", "details", "find", "get", "display", "fetch", "filter"]):
            intent_type = QueryIntentType.FILTER

        elif any(w in q for w in ["how many", "count", "number of", "total number"]):
            intent_type = QueryIntentType.COUNT

        elif metrics and metrics[0] != MetricType.COUNT:
            intent_type = QueryIntentType.AGGREGATION

        elif "longer to resolve than" in q or "compare" in q:
            intent_type = QueryIntentType.COMPARISON
            if not group_by:
                group_by.append(DimensionType.PRIORITY)
            metrics = [MetricType.AVG_RESOLUTION_TIME]

        else:
            intent_type = QueryIntentType.COUNT

        return StructuredIntent(
            intent=intent_type,
            metrics=metrics,
            group_by=group_by,
            filters=filters,
            date_range=date_range,
            sort=sort,
            limit=limit,
            anomaly_request=False,
            unresolved_only=unresolved_only,
            raw_question=question,
            confidence=0.98,
            notes="Semantic rule-based intent parsing"
        )


class AIProvider(BaseLLMProvider):
    """
    Unified AI Provider supporting:
    - xAI / Grok (via Chat Completions API)
    - Google Gemini (via Generative Language API)
    - Zero-Cost Deterministic Semantic Fallback (when no key is set or on failure)
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.provider = (provider or settings.AI_PROVIDER).lower()
        self.fallback = RuleBasedFallbackProvider()

        # Determine active provider and credentials
        if self.provider in ("gemini", "google") or (self.provider == "auto" and settings.GEMINI_API_KEY):
            self.active_provider = "gemini"
            self.api_key = api_key or settings.GEMINI_API_KEY or settings.AI_API_KEY
            self.model = model or settings.GEMINI_MODEL or settings.AI_MODEL or "gemini-1.5-flash"
        elif self.provider in ("xai", "grok") or (self.provider == "auto" and settings.XAI_API_KEY):
            self.active_provider = "grok"
            self.api_key = api_key or settings.XAI_API_KEY or settings.AI_API_KEY
            self.model = model or settings.XAI_MODEL or settings.AI_MODEL or "grok-2-latest"
        elif settings.AI_API_KEY:
            self.active_provider = "grok" if "xai" in (settings.AI_MODEL or "") else "gemini"
            self.api_key = settings.AI_API_KEY
            self.model = model or settings.AI_MODEL or "gemini-1.5-flash"
        else:
            self.active_provider = "fallback"
            self.api_key = None
            self.model = "semantic-fallback"

    async def generate_intent(self, question: str) -> StructuredIntent:
        """Route query understanding to the configured AI provider or fallback."""
        if self.active_provider == "fallback" or not self.api_key or not self.api_key.strip():
            logger.info("No AI API key configured; utilizing deterministic zero-cost semantic fallback parser.")
            return await self.fallback.generate_intent(question)

        if self.active_provider == "gemini":
            return await self._call_gemini(question)
        else:
            return await self._call_grok(question)

    async def _call_grok(self, question: str) -> StructuredIntent:
        """Call xAI Grok chat completions API."""
        logger.info(f"Calling xAI / Grok API ({self.model}) for query translation: '{question}'")
        base_url = "https://api.x.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question}
        ]
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
            "response_format": {"type": "json_object"}
        }

        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.post(base_url, json=payload, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    raw_content = data["choices"][0]["message"]["content"]
                    return parse_intent_response(raw_content, question)

            except LLMParseError as pe:
                logger.warning(f"Grok parse error on attempt {attempt + 1}: {pe}. Retrying...")
                if attempt == 1:
                    return await self.fallback.generate_intent(question)
                messages.append({"role": "assistant", "content": pe.details.get("raw_output", "")})
                messages.append({
                    "role": "user",
                    "content": "Your previous response was invalid JSON. Please return valid JSON matching StructuredIntent strictly."
                })
            except Exception as exc:
                logger.error(f"xAI API request failed: {exc}. Falling back to zero-cost parser.")
                return await self.fallback.generate_intent(question)

        return await self.fallback.generate_intent(question)

    async def _call_gemini(self, question: str) -> StructuredIntent:
        """Call Google Gemini Generative Language REST API."""
        logger.info(f"Calling Google Gemini API ({self.model}) for query translation: '{question}'")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        
        prompt_text = f"{SYSTEM_PROMPT}\n\nUser Question:\n{question}\n\nRespond with strict valid JSON only."
        payload = {
            "contents": [{"parts": [{"text": prompt_text}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.0
            }
        }

        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        raw_content = candidates[0]["content"]["parts"][0]["text"]
                        return parse_intent_response(raw_content, question)
                    else:
                        raise ValueError(f"Unexpected Gemini response structure: {data}")

            except LLMParseError as pe:
                logger.warning(f"Gemini parse error on attempt {attempt + 1}: {pe}.")
                if attempt == 1:
                    return await self.fallback.generate_intent(question)
            except Exception as exc:
                logger.error(f"Gemini API request failed: {exc}. Falling back to zero-cost parser.")
                return await self.fallback.generate_intent(question)

        return await self.fallback.generate_intent(question)


# Aliases for backward compatibility
XAIProvider = AIProvider
GeminiProvider = AIProvider
