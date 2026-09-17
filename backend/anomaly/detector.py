from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_

from backend.models.ticket import Ticket
from backend.anomaly.schemas import (
    AnomalyItem, AnomalyReport, AnomalyFilterParams, AnomalyType, AnomalySeverity
)
from backend.anomaly.rules import (
    BaseAnomalyRule, IQRResolutionTimeRule, HighPriorityUnresolvedAgedRule
)
from backend.core.logging import logger


class AnomalyDetector:
    """
    Deterministic Anomaly Detection Engine.
    
    Coordinates statistical IQR detection and SLA threshold business rules
    directly against the SQLite dataset.
    """

    def __init__(self, db: Session):
        self.db = db
        self.iqr_rule = IQRResolutionTimeRule(multiplier=1.5)
        self.aged_rule = HighPriorityUnresolvedAgedRule(age_hours_threshold=24.0)
        self.rules: List[BaseAnomalyRule] = [self.iqr_rule, self.aged_rule]

    def get_dataset_anchor_date(self) -> datetime:
        """Fetch the latest timestamp in the tickets table to anchor time calculations."""
        try:
            max_dt = self.db.execute(select(func.max(Ticket.created_at))).scalar()
            if max_dt:
                return max_dt
        except Exception as e:
            logger.warning(f"Could not retrieve max date from database: {e}")
        return datetime.utcnow()

    def detect_anomalies(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None
    ) -> AnomalyReport:
        """
        Run all statistical and business rules across matching tickets.
        """
        # 1. Fetch tickets matching boundary filters
        stmt = select(Ticket)
        conditions = []
        if start_date:
            conditions.append(Ticket.created_at >= start_date)
        if end_date:
            conditions.append(Ticket.created_at <= end_date)
        if category:
            conditions.append(Ticket.category == category)
        if priority:
            conditions.append(Ticket.priority == priority)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        tickets = list(self.db.execute(stmt).scalars().all())
        anchor_date = self.get_dataset_anchor_date()

        # 2. Evaluate all rules
        all_anomalies: List[AnomalyItem] = []
        for rule in self.rules:
            detected = rule.evaluate(tickets, anchor_date)
            all_anomalies.extend(detected)

        # 3. Sort by severity (Critical first) then metric value
        severity_weight = {
            AnomalySeverity.CRITICAL: 4,
            AnomalySeverity.HIGH: 3,
            AnomalySeverity.MEDIUM: 2,
            AnomalySeverity.LOW: 1
        }
        all_anomalies.sort(key=lambda a: (severity_weight.get(a.severity, 0), a.metric), reverse=True)

        # 4. Compute aggregation stats
        by_type: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        for item in all_anomalies:
            by_type[item.anomaly_type.value] = by_type.get(item.anomaly_type.value, 0) + 1
            by_severity[item.severity.value] = by_severity.get(item.severity.value, 0) + 1

        # Calculate dataset-wide IQR stats
        all_res_times = [
            t.resolution_time_hrs for t in tickets 
            if t.resolution_time_hrs is not None and t.resolution_time_hrs > 0
        ]
        iqr_stats = self.iqr_rule.compute_iqr_stats(all_res_times)

        return AnomalyReport(
            total_anomalies_detected=len(all_anomalies),
            anomalies_by_type=by_type,
            anomalies_by_severity=by_severity,
            iqr_statistics=iqr_stats,
            items=all_anomalies,
            detected_at=datetime.now()
        )

    def get_filtered_anomalies(self, params: AnomalyFilterParams) -> List[AnomalyItem]:
        """Retrieve anomalies with applied filtering."""
        report = self.detect_anomalies(category=params.category, priority=params.priority)
        items = report.items

        if params.anomaly_type:
            items = [a for a in items if a.anomaly_type == params.anomaly_type]
        if params.severity:
            items = [a for a in items if a.severity == params.severity]

        return items[:params.limit]

    def count_total_anomalies(self) -> int:
        """Return total count of anomalies currently flagged in dataset."""
        report = self.detect_anomalies()
        return report.total_anomalies_detected
