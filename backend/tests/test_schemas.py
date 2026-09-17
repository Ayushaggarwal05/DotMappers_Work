import pytest
from pydantic import ValidationError
from datetime import datetime
from backend.schemas.common import CategoryEnum, PriorityEnum, StatusEnum
from backend.schemas.ticket import TicketCreate, TicketFilterParams
from backend.schemas.query import (
    StructuredQuery, QueryIntent, MetricType, DimensionType,
    FilterCondition, FilterOperator, SortSpec, SortOrder
)


def test_ticket_create_validation_success():
    ticket = TicketCreate(
        ticket_id="TKT-999",
        created_at=datetime(2024, 1, 1, 12, 0),
        category=CategoryEnum.TECHNICAL,
        priority=PriorityEnum.HIGH,
        status=StatusEnum.OPEN,
        response_time_hrs=2.5,
        resolution_time_hrs=None,
        agent_id="AGT-01",
        customer_rating=None,
        issue_summary="Database connection timeout"
    )
    assert ticket.ticket_id == "TKT-999"
    assert ticket.customer_rating is None


def test_ticket_create_invalid_rating():
    with pytest.raises(ValidationError):
        TicketCreate(
            ticket_id="TKT-999",
            created_at=datetime(2024, 1, 1, 12, 0),
            category=CategoryEnum.TECHNICAL,
            priority=PriorityEnum.HIGH,
            status=StatusEnum.RESOLVED,
            response_time_hrs=2.5,
            resolution_time_hrs=10.0,
            agent_id="AGT-01",
            customer_rating=6,  # Rating must be between 1 and 5
            issue_summary="Test"
        )


def test_filter_condition_field_validation():
    # Valid field
    fc = FilterCondition(field="category", operator=FilterOperator.EQ, value="Billing")
    assert fc.field == "category"

    # Disallowed/malicious injection field
    with pytest.raises(ValidationError):
        FilterCondition(field="users; DROP TABLE tickets; --", operator=FilterOperator.EQ, value="x")


def test_structured_query_model_instantiation():
    sq = StructuredQuery(
        intent=QueryIntent.GROUPED_BREAKDOWN,
        metrics=[MetricType.COUNT, MetricType.AVG_RESPONSE_TIME],
        group_by=[DimensionType.CATEGORY],
        filters=[
            FilterCondition(field="priority", operator=FilterOperator.IN, value=["High", "Critical"])
        ],
        sort=SortSpec(field="count", order=SortOrder.DESC),
        limit=10
    )
    assert sq.intent == QueryIntent.GROUPED_BREAKDOWN
    assert len(sq.metrics) == 2
    assert sq.group_by[0] == DimensionType.CATEGORY
