from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator
from backend.schemas.common import CategoryEnum, PriorityEnum, StatusEnum


class TicketBase(BaseModel):
    """Base ticket attributes."""
    ticket_id: str = Field(..., description="Unique ticket identifier (e.g. TKT-001)")
    created_at: datetime = Field(..., description="Timestamp when ticket was created")
    category: CategoryEnum = Field(..., description="Ticket classification")
    priority: PriorityEnum = Field(..., description="Ticket priority level")
    status: StatusEnum = Field(..., description="Current status of the ticket")
    response_time_hrs: float = Field(..., ge=0.0, description="Initial response time in hours")
    resolution_time_hrs: Optional[float] = Field(None, ge=0.0, description="Resolution time in hours if resolved")
    agent_id: str = Field(..., description="Assigned agent ID (e.g. AGT-03)")
    customer_rating: Optional[int] = Field(None, ge=1, le=5, description="Customer satisfaction rating (1-5)")
    issue_summary: str = Field(..., description="Brief description or subject of the ticket")


class TicketCreate(TicketBase):
    """Schema for creating a new ticket."""
    pass


class TicketRead(TicketBase):
    """Schema for serialized ticket response."""
    model_config = ConfigDict(from_attributes=True)


class TicketFilterParams(BaseModel):
    """Query parameters for filtering tickets."""
    category: Optional[CategoryEnum] = None
    priority: Optional[PriorityEnum] = None
    status: Optional[StatusEnum] = None
    agent_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    search: Optional[str] = None
    min_rating: Optional[int] = Field(None, ge=1, le=5)
    max_rating: Optional[int] = Field(None, ge=1, le=5)
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=500)


class TicketMetrics(BaseModel):
    """Aggregated summary metrics across tickets."""
    total_tickets: int
    open_tickets: int
    resolved_tickets: int
    escalated_tickets: int
    resolution_rate_pct: float
    escalation_rate_pct: float
    avg_response_time_hrs: float
    avg_resolution_time_hrs: Optional[float]
    avg_customer_rating: Optional[float]
    sla_breach_count: int  # e.g., response_time > 4 hrs or resolution_time > 48 hrs


class IngestionStats(BaseModel):
    """Results returned from CSV ingestion."""
    total_processed: int
    inserted_count: int
    updated_count: int
    skipped_count: int
    errors: List[str]
    duration_seconds: float
