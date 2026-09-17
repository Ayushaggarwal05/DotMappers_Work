from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import numpy as np

from backend.models.ticket import Ticket
from backend.anomaly.schemas import (
    AnomalyItem, AnomalyType, AnomalySeverity
)
from backend.core.logging import logger


class BaseAnomalyRule(ABC):
    """Abstract base class for deterministic anomaly detection rules."""

    @abstractmethod
    def evaluate(self, tickets: List[Ticket], anchor_date: datetime) -> List[AnomalyItem]:
        """Evaluate rule across ticket records and return detected anomalies."""
        pass


class IQRResolutionTimeRule(BaseAnomalyRule):
    """
    Statistical Outlier Detection for Resolution Times using the Interquartile Range (IQR).
    
    Formula:
      Q1 = 25th percentile
      Q3 = 75th percentile
      IQR = Q3 - Q1
      Upper Bound = Q3 + 1.5 * IQR
      Extreme Bound = Q3 + 3.0 * IQR
    """

    def __init__(self, multiplier: float = 1.5):
        self.multiplier = multiplier

    def compute_iqr_stats(self, resolution_times: List[float]) -> Dict[str, float]:
        """Compute statistical bounds from valid resolution times."""
        if not resolution_times:
            return {
                "count": 0, "q1": 0.0, "median": 0.0, "q3": 0.0,
                "iqr": 0.0, "upper_bound": 0.0, "extreme_bound": 0.0
            }

        arr = np.array(resolution_times)
        q1 = float(np.percentile(arr, 25))
        median = float(np.median(arr))
        q3 = float(np.percentile(arr, 75))
        iqr = q3 - q1
        upper_bound = q3 + (self.multiplier * iqr)
        extreme_bound = q3 + (3.0 * iqr)

        return {
            "count": len(resolution_times),
            "q1": round(q1, 2),
            "median": round(median, 2),
            "q3": round(q3, 2),
            "iqr": round(iqr, 2),
            "upper_bound": round(upper_bound, 2),
            "extreme_bound": round(extreme_bound, 2)
        }

    def evaluate(self, tickets: List[Ticket], anchor_date: datetime) -> List[AnomalyItem]:
        # Extract resolution times from resolved tickets with valid numeric times
        res_times = [
            t.resolution_time_hrs for t in tickets 
            if t.resolution_time_hrs is not None and t.resolution_time_hrs > 0
        ]
        
        if len(res_times) < 5:
            return []

        stats = self.compute_iqr_stats(res_times)
        upper_bound = stats["upper_bound"]
        extreme_bound = stats["extreme_bound"]

        anomalies = []
        for t in tickets:
            if t.resolution_time_hrs is not None and t.resolution_time_hrs > upper_bound:
                val = round(t.resolution_time_hrs, 2)
                severity = AnomalySeverity.CRITICAL if val >= extreme_bound else AnomalySeverity.HIGH
                reason = (
                    f"Resolution time ({val} hrs) exceeds the statistical IQR upper bound ({upper_bound} hrs, "
                    f"Q1={stats['q1']}h, Q3={stats['q3']}h, IQR={stats['iqr']}h)."
                )
                anomalies.append(
                    AnomalyItem(
                        ticket_id=t.ticket_id,
                        anomaly_type=AnomalyType.LONG_RESOLUTION_TIME,
                        severity=severity,
                        reason=reason,
                        metric=val,
                        threshold=upper_bound,
                        created_at=t.created_at,
                        category=t.category,
                        priority=t.priority,
                        status=t.status,
                        agent_id=t.agent_id,
                        issue_summary=t.issue_summary
                    )
                )

        return anomalies


class HighPriorityUnresolvedAgedRule(BaseAnomalyRule):
    """
    Flags High and Critical tickets that remain unresolved (Open / Escalated)
    longer than 24 hours from creation.
    """

    def __init__(self, age_hours_threshold: float = 24.0):
        self.age_hours_threshold = age_hours_threshold

    def evaluate(self, tickets: List[Ticket], anchor_date: datetime) -> List[AnomalyItem]:
        anomalies = []
        for t in tickets:
            # Check high or critical priority and unresolved status
            if t.priority in ("High", "Critical") and t.status in ("Open", "Escalated"):
                age_timedelta = anchor_date - t.created_at
                age_hours = round(age_timedelta.total_seconds() / 3600.0, 1)

                if age_hours > self.age_hours_threshold:
                    severity = AnomalySeverity.CRITICAL if t.priority == "Critical" else AnomalySeverity.HIGH
                    reason = (
                        f"{t.priority} priority ticket has remained unresolved ({t.status}) "
                        f"for {age_hours} hours, exceeding the {self.age_hours_threshold}h SLA threshold."
                    )
                    anomalies.append(
                        AnomalyItem(
                            ticket_id=t.ticket_id,
                            anomaly_type=AnomalyType.UNRESOLVED_HIGH_PRIORITY_AGED,
                            severity=severity,
                            reason=reason,
                            metric=age_hours,
                            threshold=self.age_hours_threshold,
                            created_at=t.created_at,
                            category=t.category,
                            priority=t.priority,
                            status=t.status,
                            agent_id=t.agent_id,
                            issue_summary=t.issue_summary
                        )
                    )

        return anomalies
