from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.api.dependencies import get_ticket_service, get_ingestion_service
from backend.services.ticket_service import TicketService
from backend.services.ingestion_service import IngestionService
from backend.schemas.common import (
    ApiResponse, PaginatedResponse, CategoryEnum, PriorityEnum, StatusEnum
)
from backend.schemas.ticket import (
    TicketRead, TicketFilterParams, TicketMetrics, IngestionStats
)
from backend.schemas.query import StructuredQuery, StructuredQueryResult

router = APIRouter(prefix="/tickets", tags=["Tickets"])


@router.get("", response_model=ApiResponse[PaginatedResponse[TicketRead]])
def list_tickets(
    category: Optional[CategoryEnum] = Query(None, description="Filter by category"),
    priority: Optional[PriorityEnum] = Query(None, description="Filter by priority"),
    status: Optional[StatusEnum] = Query(None, description="Filter by status"),
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    search: Optional[str] = Query(None, description="Search in summary, id, or agent"),
    start_date: Optional[datetime] = Query(None, description="Filter tickets created after"),
    end_date: Optional[datetime] = Query(None, description="Filter tickets created before"),
    min_rating: Optional[int] = Query(None, ge=1, le=5, description="Min customer rating"),
    max_rating: Optional[int] = Query(None, ge=1, le=5, description="Max customer rating"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page"),
    service: TicketService = Depends(get_ticket_service)
):
    """Retrieve filtered and paginated support tickets."""
    params = TicketFilterParams(
        category=category,
        priority=priority,
        status=status,
        agent_id=agent_id,
        search=search,
        start_date=start_date,
        end_date=end_date,
        min_rating=min_rating,
        max_rating=max_rating,
        page=page,
        page_size=page_size
    )
    result = service.list_tickets(params)
    return ApiResponse(data=result, message=f"Retrieved {len(result.items)} tickets")


@router.get("/analytics/summary", response_model=ApiResponse[TicketMetrics])
def get_analytics_summary(
    category: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    service: TicketService = Depends(get_ticket_service)
):
    """Get aggregated summary metrics across tickets."""
    metrics = service.get_metrics_summary(
        category=category,
        priority=priority,
        agent_id=agent_id,
        start_date=start_date,
        end_date=end_date
    )
    return ApiResponse(data=metrics, message="Metrics computed successfully")


@router.post("/query", response_model=ApiResponse[StructuredQueryResult])
def execute_structured_query(
    query: StructuredQuery,
    service: TicketService = Depends(get_ticket_service)
):
    """
    Execute a validated structured analytics query deterministically.
    This endpoint powers the safe execution layer for the natural language pipeline.
    """
    result = service.execute_structured_query(query)
    return ApiResponse(data=result, message="Query executed successfully")


@router.post("/ingest", response_model=ApiResponse[IngestionStats])
def trigger_ingestion(
    service: IngestionService = Depends(get_ingestion_service)
):
    """Trigger ingestion of the dataset from the configured CSV path."""
    stats = service.ingest_from_file()
    return ApiResponse(
        data=stats,
        message=f"Ingested {stats.inserted_count} new tickets, {stats.updated_count} updated."
    )


@router.get("/{ticket_id}", response_model=ApiResponse[TicketRead])
def get_ticket(
    ticket_id: str,
    service: TicketService = Depends(get_ticket_service)
):
    """Retrieve details for a single support ticket."""
    ticket = service.get_ticket(ticket_id)
    return ApiResponse(data=ticket, message="Ticket retrieved")
