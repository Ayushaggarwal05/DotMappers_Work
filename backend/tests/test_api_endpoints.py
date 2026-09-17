import pytest


def test_get_stats_endpoint(client, populated_db):
    """Verify GET /api/stats returns accurate metrics from dataset."""
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    
    stats = data["data"]
    assert stats["total_tickets"] == 500
    assert stats["open_tickets"] == 111
    assert stats["resolved_tickets"] == 327
    assert stats["escalated_tickets"] == 62
    assert stats["critical_tickets"] > 0
    assert stats["average_response_time"] > 0.0
    assert stats["average_resolution_time"] > 0.0
    assert 1.0 <= stats["average_customer_rating"] <= 5.0
    assert stats["anomaly_count"] > 0


def test_get_anomalies_endpoint(client, populated_db):
    """Verify GET /api/anomalies returns flagged anomalies with statistics."""
    response = client.get("/api/anomalies?limit=25")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    
    report = data["data"]
    assert report["total_anomalies_detected"] > 0
    assert len(report["items"]) <= 25
    assert "iqr_statistics" in report
    
    # Verify each anomaly item structure
    item = report["items"][0]
    assert "ticket_id" in item
    assert "anomaly_type" in item
    assert "severity" in item
    assert "reason" in item
    assert "metric" in item


def test_get_anomalies_with_filters(client, populated_db):
    """Verify GET /api/anomalies filtering by anomaly_type and severity."""
    response = client.get("/api/anomalies?anomaly_type=long_resolution_time")
    assert response.status_code == 200
    data = response.json()
    for item in data["data"]["items"]:
        assert item["anomaly_type"] == "long_resolution_time"


def test_get_tickets_pagination_and_filters(client, populated_db):
    """Verify GET /api/tickets pagination and category filtering."""
    response = client.get("/api/tickets?category=Technical&page=1&page_size=15")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["data"]["items"]) == 15
    assert data["data"]["total"] == 152  # 152 technical tickets in 500-row dataset
    for item in data["data"]["items"]:
        assert item["category"] == "Technical"


def test_get_single_ticket_success(client, populated_db):
    """Verify GET /api/tickets/{ticket_id} for existing ticket."""
    response = client.get("/api/tickets/TKT-001")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["ticket_id"] == "TKT-001"
    assert data["data"]["category"] == "General"


def test_get_single_ticket_not_found(client, populated_db):
    """Verify GET /api/tickets/{ticket_id} returns 404 for nonexistent ticket."""
    response = client.get("/api/tickets/NONEXISTENT-999")
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert data["error"]["type"] == "NotFoundError"


def test_query_missing_question_payload_validation(client, populated_db):
    """Verify POST /api/query rejects invalid or empty payload."""
    response = client.post("/api/query", json={"question": ""})
    assert response.status_code == 422
