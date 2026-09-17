from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, func, case
from pydantic import BaseModel
from typing import Optional, Dict, Any

from backend.core.database import get_db
from backend.models.ticket import Ticket
from backend.anomaly.detector import AnomalyDetector
from backend.schemas.common import ApiResponse

router = APIRouter(prefix="/stats", tags=["Dashboard Statistics"])


class DashboardStats(BaseModel):
    """Overall dashboard statistics calculated from database."""
    total_tickets: int
    open_tickets: int
    resolved_tickets: int
    escalated_tickets: int
    critical_tickets: int
    average_response_time: float
    average_resolution_time: Optional[float]
    average_customer_rating: Optional[float]
    anomaly_count: int
    sla_breach_count: int


@router.get("", response_model=ApiResponse[DashboardStats])
def get_dashboard_stats(db: Session = Depends(get_db)):
    """
    Retrieve live dashboard KPI metrics calculated deterministically from SQLite.
    """
    stmt = select(
        func.count().label("total"),
        func.sum(case((Ticket.status == "Open", 1), else_=0)).label("open_count"),
        func.sum(case((Ticket.status == "Resolved", 1), else_=0)).label("resolved_count"),
        func.sum(case((Ticket.status == "Escalated", 1), else_=0)).label("escalated_count"),
        func.sum(case((Ticket.priority == "Critical", 1), else_=0)).label("critical_count"),
        func.avg(Ticket.response_time_hrs).label("avg_response"),
        func.avg(Ticket.resolution_time_hrs).label("avg_resolution"),
        func.avg(Ticket.customer_rating).label("avg_rating"),
        func.sum(case((Ticket.response_time_hrs > 4.0, 1), else_=0)).label("sla_breaches")
    )
    row = db.execute(stmt).one()

    # Count real anomalies from detector
    detector = AnomalyDetector(db)
    anomaly_count = detector.count_total_anomalies()

    total = row.total or 0
    stats = DashboardStats(
        total_tickets=total,
        open_tickets=row.open_count or 0,
        resolved_tickets=row.resolved_count or 0,
        escalated_tickets=row.escalated_count or 0,
        critical_tickets=row.critical_count or 0,
        average_response_time=round(float(row.avg_response), 2) if row.avg_response is not None else 0.0,
        average_resolution_time=round(float(row.avg_resolution), 2) if row.avg_resolution is not None else None,
        average_customer_rating=round(float(row.avg_rating), 2) if row.avg_rating is not None else None,
        anomaly_count=anomaly_count,
        sla_breach_count=row.sla_breaches or 0
    )

    return ApiResponse(data=stats, message="Dashboard statistics computed successfully")
