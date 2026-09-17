from datetime import datetime
from backend.repositories.ticket_repository import TicketRepository
from backend.schemas.ticket import TicketFilterParams
from backend.schemas.common import CategoryEnum, PriorityEnum, StatusEnum


def test_repository_get_by_id(populated_db):
    repo = TicketRepository(populated_db)
    ticket = repo.get_by_id("TKT-001")
    assert ticket is not None
    assert ticket.ticket_id == "TKT-001"
    assert ticket.category == "General"
    assert ticket.priority == "Low"
    assert ticket.status == "Resolved"
    assert ticket.agent_id == "AGT-03"


def test_repository_filtering_by_category_and_status(populated_db):
    repo = TicketRepository(populated_db)
    
    params = TicketFilterParams(
        category=CategoryEnum.BILLING,
        status=StatusEnum.RESOLVED,
        page=1,
        page_size=20
    )
    items, total = repo.filter_tickets(params)
    assert total > 0
    assert len(items) <= 20
    for item in items:
        assert item.category == "Billing"
        assert item.status == "Resolved"


def test_repository_metrics_calculation(populated_db):
    repo = TicketRepository(populated_db)
    metrics = repo.get_overall_metrics()

    assert metrics.total_tickets == 500
    assert metrics.open_tickets + metrics.resolved_tickets + metrics.escalated_tickets == 500
    assert metrics.resolution_rate_pct > 0.0
    assert metrics.avg_response_time_hrs > 0.0
    assert metrics.avg_customer_rating is not None
    assert 1.0 <= metrics.avg_customer_rating <= 5.0
    assert metrics.sla_breach_count >= 0
