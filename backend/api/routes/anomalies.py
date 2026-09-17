from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.anomaly.detector import AnomalyDetector
from backend.anomaly.schemas import (
    AnomalyReport, AnomalyItem, AnomalyType, AnomalySeverity, AnomalyFilterParams
)
from backend.schemas.common import ApiResponse

router = APIRouter(prefix="/anomalies", tags=["Anomaly Detection"])


@router.get("", response_model=ApiResponse[AnomalyReport])
def get_anomalies(
    anomaly_type: Optional[AnomalyType] = Query(None, description="Filter by anomaly type"),
    severity: Optional[AnomalySeverity] = Query(None, description="Filter by severity"),
    priority: Optional[str] = Query(None, description="Filter by ticket priority"),
    category: Optional[str] = Query(None, description="Filter by ticket category"),
    limit: int = Query(100, ge=1, le=1000, description="Max anomalies returned"),
    db: Session = Depends(get_db)
):
    """
    Retrieve statistically detected anomalies and SLA violations across support tickets.
    
    Includes:
    - Long resolution times flagged via statistical IQR upper bounds.
    - High/Critical priority unresolved tickets aged >24 hours.
    """
    detector = AnomalyDetector(db)
    params = AnomalyFilterParams(
        anomaly_type=anomaly_type,
        severity=severity,
        priority=priority,
        category=category,
        limit=limit
    )
    report = detector.detect_anomalies(category=category, priority=priority)

    # Filter items if specific type or severity requested
    filtered_items = report.items
    if anomaly_type:
        filtered_items = [item for item in filtered_items if item.anomaly_type == anomaly_type]
    if severity:
        filtered_items = [item for item in filtered_items if item.severity == severity]

    report.items = filtered_items[:limit]

    return ApiResponse(
        data=report,
        message=f"Retrieved {len(report.items)} anomalies (total flagged: {report.total_anomalies_detected})"
    )
