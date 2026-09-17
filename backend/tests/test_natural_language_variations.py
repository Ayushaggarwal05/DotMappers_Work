import pytest


def test_q1_variations_open_tickets(client, populated_db):
    """Test phrasing variations for open tickets."""
    variations = [
        "How many tickets are currently open?",
        "Total number of open tickets?",
        "Count of tickets that are open",
        "How many active open tickets exist?"
    ]
    for q in variations:
        resp = client.post("/api/query", json={"question": q})
        assert resp.status_code == 200
        data = resp.json()
        assert data["interpretation"]["intent"] == "count"
        assert data["metadata"]["total_records_matched"] == 111


def test_q2_variations_top_agent(client, populated_db):
    """Test phrasing variations for agent ranking."""
    variations = [
        "Which agent resolved the most tickets this month?",
        "Top agent with the most resolved tickets this month",
        "Who is the leading agent for resolved tickets this month?"
    ]
    for q in variations:
        resp = client.post("/api/query", json={"question": q})
        assert resp.status_code == 200
        data = resp.json()
        assert data["interpretation"]["intent"] == "top_n"
        assert len(data["data"]) >= 1
        assert "agent_id" in data["data"][0]


def test_q3_variations_critical_slow_resolution(client, populated_db):
    """Test phrasing variations for critical tickets not resolved within 12h."""
    variations = [
        "Show me all Critical tickets not resolved within 12 hours.",
        "List critical priority tickets taking longer than 12 hours to resolve",
        "Find Critical tickets taking more than 12 hours"
    ]
    for q in variations:
        resp = client.post("/api/query", json={"question": q})
        assert resp.status_code == 200
        data = resp.json()
        assert data["interpretation"]["intent"] == "filter"
        for rec in data["data"]:
            assert rec["priority"] == "Critical"
            if rec["resolution_time_hrs"] is not None:
                assert rec["resolution_time_hrs"] > 12.0


def test_q4_variations_technical_rating(client, populated_db):
    """Test phrasing variations for average rating in Technical category."""
    variations = [
        "What is the average customer rating for Technical category tickets?",
        "Average customer rating for technical issues?",
        "Average rating for technical tickets"
    ]
    for q in variations:
        resp = client.post("/api/query", json={"question": q})
        assert resp.status_code == 200
        data = resp.json()
        assert data["interpretation"]["intent"] == "aggregation"
        assert "avg_rating" in data["data"][0]
        assert 3.5 <= data["data"][0]["avg_rating"] <= 4.0


def test_q5_variations_anomalies(client, populated_db):
    """Test phrasing variations for anomaly detection requests."""
    variations = [
        "Are there any anomalies in resolution times this week?",
        "Detect outliers in resolution times this week",
        "Show resolution time anomalies this week"
    ]
    for q in variations:
        resp = client.post("/api/query", json={"question": q})
        assert resp.status_code == 200
        data = resp.json()
        assert data["metadata"]["is_anomaly_request"] is True
        assert "anomalies_by_type" in data["metadata"]
