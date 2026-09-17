from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class AnomalyType(str, Enum):
    """Types of detected anomalies."""
    LONG_RESOLUTION_TIME = "long_resolution_time"
    UNRESOLVED_HIGH_PRIORITY_AGED = "unresolved_high_priority_aged"
    ABNORMAL_RESPONSE_TIME = "abnormal_response_time"


class AnomalySeverity(str, Enum):
    """Severity classification for anomalies."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyItem(BaseModel):
    """Detailed anomaly record flagged on a specific ticket."""
    ticket_id: str
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    reason: str
    metric: float
    threshold: Optional[float] = None
    created_at: datetime
    category: str
    priority: str
    status: str
    agent_id: str
    issue_summary: str


class AnomalyReport(BaseModel):
    """Aggregated anomaly detection summary report."""
    total_anomalies_detected: int
    anomalies_by_type: Dict[str, int]
    anomalies_by_severity: Dict[str, int]
    iqr_statistics: Dict[str, Any]
    items: List[AnomalyItem]
    detected_at: datetime = Field(default_factory=datetime.now)


class AnomalyFilterParams(BaseModel):
    """Filter parameters for querying anomalies."""
    anomaly_type: Optional[AnomalyType] = None
    severity: Optional[AnomalySeverity] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    limit: int = Field(100, ge=1, le=1000)
