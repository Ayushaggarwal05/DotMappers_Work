from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, func, case
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

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


class BreakdownItem(BaseModel):
    name: str
    count: int
    percentage: Optional[float] = None


class DashboardBreakdown(BaseModel):
    """Distribution metrics for visual dashboard charts."""
    by_category: List[Dict[str, Any]]
    by_priority: List[Dict[str, Any]]
    by_status: List[Dict[str, Any]]
    by_agent: List[Dict[str, Any]]
    rating_distribution: List[Dict[str, Any]]


@router.get("/breakdown", response_model=ApiResponse[DashboardBreakdown])
def get_dashboard_breakdown(db: Session = Depends(get_db)):
    """
    Retrieve dimensional breakdown datasets for visualization charts.
    """
    # 1. By Category
    cat_rows = db.execute(
        select(Ticket.category, func.count().label("count"))
        .group_by(Ticket.category)
        .order_by(func.count().desc())
    ).all()
    by_category = [{"category": row[0], "count": row[1]} for row in cat_rows]

    # 2. By Priority
    prio_rows = db.execute(
        select(Ticket.priority, func.count().label("count"))
        .group_by(Ticket.priority)
        .order_by(func.count().desc())
    ).all()
    by_priority = [{"priority": row[0], "count": row[1]} for row in prio_rows]

    # 3. By Status
    status_rows = db.execute(
        select(Ticket.status, func.count().label("count"))
        .group_by(Ticket.status)
        .order_by(func.count().desc())
    ).all()
    by_status = [{"status": row[0], "count": row[1]} for row in status_rows]

    # 4. By Agent
    agent_rows = db.execute(
        select(Ticket.agent_id, func.count().label("count"))
        .group_by(Ticket.agent_id)
        .order_by(func.count().desc())
    ).all()
    by_agent = [{"agent_id": row[0], "count": row[1]} for row in agent_rows]

    # 5. Rating Distribution
    rating_rows = db.execute(
        select(Ticket.customer_rating, func.count().label("count"))
        .where(Ticket.customer_rating.isnot(None))
        .group_by(Ticket.customer_rating)
        .order_by(Ticket.customer_rating.asc())
    ).all()
    rating_distribution = [{"rating": f"{row[0]} ⭐", "count": row[1]} for row in rating_rows]

    breakdown = DashboardBreakdown(
        by_category=by_category,
        by_priority=by_priority,
        by_status=by_status,
        by_agent=by_agent,
        rating_distribution=rating_distribution
    )

    return ApiResponse(data=breakdown, message="Dashboard breakdown computed successfully")
