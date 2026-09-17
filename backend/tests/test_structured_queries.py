from backend.repositories.ticket_repository import TicketRepository
from backend.schemas.query import (
    StructuredQuery, QueryIntent, MetricType, DimensionType,
    FilterCondition, FilterOperator, SortSpec, SortOrder
)


def test_execute_structured_query_aggregation(populated_db):
    """Test deterministic execution of structured query for average resolution time."""
    repo = TicketRepository(populated_db)
    
    query = StructuredQuery(
        intent=QueryIntent.METRIC_AGGREGATION,
        metrics=[MetricType.COUNT, MetricType.AVG_RESOLUTION_TIME, MetricType.AVG_RATING],
        filters=[
            FilterCondition(field="status", operator=FilterOperator.EQ, value="Resolved")
        ]
    )
    result = repo.execute_structured_query(query)
    
    assert result.total_records_matched > 0
    assert "count" in result.metrics_summary
    assert "avg_resolution_time" in result.metrics_summary
    assert "avg_rating" in result.metrics_summary
    assert result.metrics_summary["count"] == result.total_records_matched
    assert result.execution_time_ms >= 0


def test_execute_structured_query_group_by_category(populated_db):
    """Test deterministic execution of breakdown by category."""
    repo = TicketRepository(populated_db)
    
    query = StructuredQuery(
        intent=QueryIntent.GROUPED_BREAKDOWN,
        metrics=[MetricType.COUNT, MetricType.AVG_RESPONSE_TIME],
        group_by=[DimensionType.CATEGORY],
        sort=SortSpec(field="count", order=SortOrder.DESC)
    )
    result = repo.execute_structured_query(query)

    assert result.total_records_matched == 500
    assert len(result.breakdown_data) == 3  # Billing, Technical, General
    
    categories = {row["category"] for row in result.breakdown_data}
    assert categories == {"Billing", "Technical", "General"}
    
    # Verify sorted descending by count
    counts = [row["count"] for row in result.breakdown_data]
    assert counts == sorted(counts, reverse=True)


def test_execute_structured_query_api_endpoint(client, populated_db):
    """Test API endpoint POST /api/v1/tickets/query."""
    payload = {
        "intent": "GROUPED_BREAKDOWN",
        "metrics": ["count", "avg_rating"],
        "group_by": ["priority"],
        "filters": [
            {"field": "status", "operator": "eq", "value": "Resolved"}
        ]
    }
    response = client.post("/api/v1/tickets/query", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert len(data["data"]["breakdown_data"]) > 0
