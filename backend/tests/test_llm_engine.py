import pytest
from datetime import datetime
from backend.llm.parser import parse_intent_response, clean_json_text, LLMParseError
from backend.llm.xai_provider import RuleBasedFallbackProvider
from backend.query_engine.intent_schema import (
    StructuredIntent, QueryIntentType, MetricType, DimensionType,
    FilterOperator, FilterClause
)
from backend.query_engine.validator import IntentValidator
from backend.query_engine.executor import QueryExecutor


def test_clean_json_text_markdown_stripping():
    """Verify markdown code blocks and surrounding text are correctly stripped."""
    raw = '```json\n{"intent": "count", "raw_question": "test"}\n```'
    cleaned = clean_json_text(raw)
    assert cleaned == '{"intent": "count", "raw_question": "test"}'

    raw_with_text = 'Here is the JSON:\n```json\n{"intent": "filter", "raw_question": "test"}\n```\nHope this helps!'
    cleaned2 = clean_json_text(raw_with_text)
    assert cleaned2 == '{"intent": "filter", "raw_question": "test"}'


def test_parse_intent_response_valid():
    raw = """
    {
      "intent": "aggregation",
      "metrics": ["avg_rating"],
      "filters": [{"field": "category", "operator": "eq", "value": "Technical"}],
      "raw_question": "What is the average rating for Technical tickets?"
    }
    """
    intent = parse_intent_response(raw, "What is the average rating for Technical tickets?")
    assert intent.intent == QueryIntentType.AGGREGATION
    assert intent.metrics == [MetricType.AVG_RATING]
    assert intent.filters[0].field == "category"
    assert intent.filters[0].value == "Technical"


def test_parse_intent_response_invalid_json():
    with pytest.raises(LLMParseError):
        parse_intent_response("Invalid non-json string {broken", "test")


def test_parse_intent_response_schema_violation():
    with pytest.raises(LLMParseError):
        # Disallowed field or operator
        parse_intent_response('{"intent": "fake_intent", "raw_question": "test"}', "test")


@pytest.mark.asyncio
async def test_rule_based_fallback_assessment_questions():
    provider = RuleBasedFallbackProvider()

    # 1. Count open tickets
    i1 = await provider.generate_intent("How many tickets are currently open?")
    assert i1.intent == QueryIntentType.COUNT
    assert any(f.field == "status" and f.value == "Open" for f in i1.filters)

    # 2. Agent ranking
    i2 = await provider.generate_intent("Which agent resolved the most tickets this month?")
    assert i2.intent == QueryIntentType.TOP_N
    assert DimensionType.AGENT_ID in i2.group_by
    assert any(f.field == "status" and f.value == "Resolved" for f in i2.filters)
    assert i2.date_range is not None

    # 3. Filter critical tickets > 12 hours
    i3 = await provider.generate_intent("Show me all Critical tickets not resolved within 12 hours.")
    assert i3.intent == QueryIntentType.FILTER
    assert any(f.field == "priority" and f.value == "Critical" for f in i3.filters)
    assert any(f.field == "resolution_time_hrs" and f.operator == FilterOperator.GT and f.value == 12.0 for f in i3.filters)

    # 4. Aggregation rating for technical
    i4 = await provider.generate_intent("What is the average customer rating for Technical category tickets?")
    assert i4.intent == QueryIntentType.AGGREGATION
    assert MetricType.AVG_RATING in i4.metrics
    assert any(f.field == "category" and f.value == "Technical" for f in i4.filters)

    # 5. Anomaly detection
    i5 = await provider.generate_intent("Are there any anomalies in resolution times this week?")
    assert i5.intent == QueryIntentType.ANOMALY_DETECTION
    assert i5.anomaly_request is True
