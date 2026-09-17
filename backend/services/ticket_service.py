from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from backend.repositories.ticket_repository import TicketRepository
from backend.schemas.common import PaginatedResponse
from backend.schemas.ticket import TicketFilterParams, TicketRead, TicketMetrics
from backend.schemas.query import StructuredQuery, StructuredQueryResult
from backend.core.exceptions import NotFoundError
from backend.core.logging import logger


class TicketService:
    """High-level domain service for customer support tickets and analytics."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = TicketRepository(db)

    def get_ticket(self, ticket_id: str) -> TicketRead:
        """Fetch a specific ticket by ticket ID."""
        ticket = self.repository.get_by_id(ticket_id)
        if not ticket:
            raise NotFoundError(f"Ticket with ID '{ticket_id}' not found", details={"ticket_id": ticket_id})
        return TicketRead.model_validate(ticket)

    def list_tickets(self, params: TicketFilterParams) -> PaginatedResponse[TicketRead]:
        """List and filter tickets with pagination."""
        items, total = self.repository.filter_tickets(params)
        total_pages = (total + params.page_size - 1) // params.page_size if total > 0 else 1
        
        return PaginatedResponse(
            items=[TicketRead.model_validate(item) for item in items],
            total=total,
            page=params.page,
            page_size=params.page_size,
            total_pages=total_pages
        )

    def get_metrics_summary(
        self,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        agent_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> TicketMetrics:
        """Get aggregate ticket metrics."""
        return self.repository.get_overall_metrics(
            category=category,
            priority=priority,
            agent_id=agent_id,
            start_date=start_date,
            end_date=end_date
        )

    def execute_structured_query(self, query: StructuredQuery) -> StructuredQueryResult:
        """Safely execute a structured query spec against the database."""
        logger.info(f"Executing structured query with intent: {query.intent.value}")
        return self.repository.execute_structured_query(query)
