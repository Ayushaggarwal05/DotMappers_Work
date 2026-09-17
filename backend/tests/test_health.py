def test_health_endpoint_success(client, populated_db):
    """Verify /health returns 200 with accurate status, db, and dataset metadata."""
    response = client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert "uptime_seconds" in data
    assert data["database"]["connected"] is True
    assert data["database"]["engine"] == "sqlite"
    assert data["dataset"]["file_exists"] is True
    assert data["dataset"]["loaded_ticket_count"] >= 500


def test_api_v1_health_endpoint(client):
    """Verify /api/v1/health prefix route also works."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["database"]["connected"] is True
