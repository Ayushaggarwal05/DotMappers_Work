import pytest
from backend.anomaly.detector import AnomalyDetector
from backend.anomaly.rules import IQRResolutionTimeRule, HighPriorityUnresolvedAgedRule
from backend.anomaly.schemas import AnomalyType, AnomalySeverity, AnomalyFilterParams


def test_iqr_resolution_time_rule(populated_db):
    """Verify statistical IQR calculation correctly flags resolution time outliers."""
    detector = AnomalyDetector(populated_db)
    report = detector.detect_anomalies()

    assert report.total_anomalies_detected > 0
    assert "long_resolution_time" in report.anomalies_by_type
    
    # Check IQR stats
    iqr_stats = report.iqr_statistics
    assert iqr_stats["count"] > 0
    assert iqr_stats["q1"] > 0
    assert iqr_stats["q3"] >= iqr_stats["q1"]
    assert iqr_stats["upper_bound"] > iqr_stats["q3"]

    # Verify all long resolution time anomalies exceed upper_bound
    upper_bound = iqr_stats["upper_bound"]
    long_items = [item for item in report.items if item.anomaly_type == AnomalyType.LONG_RESOLUTION_TIME]
    assert len(long_items) > 0
    for item in long_items:
        assert item.metric > upper_bound
        assert item.threshold == upper_bound


def test_high_priority_unresolved_aged_rule(populated_db):
    """Verify detection of High/Critical unresolved tickets aged >24 hours."""
    detector = AnomalyDetector(populated_db)
    report = detector.detect_anomalies()

    assert "unresolved_high_priority_aged" in report.anomalies_by_type
    aged_items = [item for item in report.items if item.anomaly_type == AnomalyType.UNRESOLVED_HIGH_PRIORITY_AGED]
    assert len(aged_items) > 0

    for item in aged_items:
        assert item.priority in ("High", "Critical")
        assert item.status in ("Open", "Escalated")
        assert item.metric > 24.0


def test_get_filtered_anomalies(populated_db):
    """Verify filtering anomalies by type and severity."""
    detector = AnomalyDetector(populated_db)
    
    params = AnomalyFilterParams(
        anomaly_type=AnomalyType.LONG_RESOLUTION_TIME,
        limit=10
    )
    items = detector.get_filtered_anomalies(params)
    assert len(items) <= 10
    for item in items:
        assert item.anomaly_type == AnomalyType.LONG_RESOLUTION_TIME
