import pytest


def test_nl_query_1_open_tickets_count(client, populated_db):
    """Q1: How many tickets are currently open?"""
    response = client.post("/api/query", json={"question": "How many tickets are currently open?"})
    assert response.status_code == 200
    
    data = response.json()
    assert data["question"] == "How many tickets are currently open?"
    assert data["interpretation"]["intent"] == "count"
    assert data["metadata"]["is_anomaly_request"] is False
    assert data["metadata"]["total_records_matched"] == 111  # Exact count from 500-row dataset
    assert "111" in data["answer"]
    assert data["data"][0]["count"] == 111


def test_nl_query_2_top_agent_resolved_month(client, populated_db):
    """Q2: Which agent resolved the most tickets this month?"""
    response = client.post("/api/query", json={"question": "Which agent resolved the most tickets this month?"})
    assert response.status_code == 200
    
    data = response.json()
    assert data["interpretation"]["intent"] == "top_n"
    assert data["metadata"]["is_anomaly_request"] is False
    assert len(data["data"]) >= 1
    assert "agent_id" in data["data"][0]
    assert "AGT-" in data["answer"]


def test_nl_query_3_critical_not_resolved_within_12_hours(client, populated_db):
    """Q3: Show me all Critical tickets not resolved within 12 hours."""
    response = client.post("/api/query", json={"question": "Show me all Critical tickets not resolved within 12 hours."})
    assert response.status_code == 200
    
    data = response.json()
    assert data["interpretation"]["intent"] == "filter"
    assert data["metadata"]["is_anomaly_request"] is False
    # Verify all returned records have priority=Critical and resolution_time_hrs > 12.0
    for record in data["data"]:
        assert record["priority"] == "Critical"
        if record["resolution_time_hrs"] is not None:
            assert record["resolution_time_hrs"] > 12.0


def test_nl_query_4_avg_customer_rating_technical(client, populated_db):
    """Q4: What is the average customer rating for Technical category tickets?"""
    response = client.post("/api/query", json={"question": "What is the average customer rating for Technical category tickets?"})
    assert response.status_code == 200
    
    data = response.json()
    assert data["interpretation"]["intent"] == "aggregation"
    assert data["metadata"]["is_anomaly_request"] is False
    assert "avg_rating" in data["data"][0]
    avg_rating = data["data"][0]["avg_rating"]
    assert 3.5 <= avg_rating <= 4.0
    assert str(avg_rating) in data["answer"]


def test_nl_query_5_anomaly_detection_routing(client, populated_db):
    """Q5: Are there any anomalies in resolution times this week?"""
    response = client.post("/api/query", json={"question": "Are there any anomalies in resolution times this week?"})
    assert response.status_code == 200
    
    data = response.json()
    assert data["interpretation"]["intent"] == "anomaly_detection"
    assert data["metadata"]["is_anomaly_request"] is True
    assert "anomalies_by_type" in data["metadata"]
    assert "iqr_statistics" in data["metadata"]
    assert "anomalies" in data["answer"].lower() or "no anomalies" in data["answer"].lower()


def test_nl_query_critical_unresolved(client, populated_db):
    """Test 'How many critical tickets are unresolved?'"""
    response = client.post("/api/query", json={"question": "How many critical tickets are unresolved?"})
    assert response.status_code == 200
    data = response.json()
    assert data["interpretation"]["intent"] == "count"
    assert data["metadata"]["total_records_matched"] > 0


def test_nl_query_group_by_category_avg_rating(client, populated_db):
    """Test 'What is the average rating by category?'"""
    response = client.post("/api/query", json={"question": "What is the average rating by category?"})
    assert response.status_code == 200
    data = response.json()
    assert data["interpretation"]["intent"] == "group_by"
    assert len(data["data"]) == 3  # Billing, Technical, General
    for row in data["data"]:
        assert "category" in row
        assert "avg_rating" in row


def test_nl_query_comparison_priority_resolution(client, populated_db):
    """Test 'Are critical tickets taking longer to resolve than high priority tickets?'"""
    response = client.post("/api/query", json={"question": "Are critical tickets taking longer to resolve than high priority tickets?"})
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) > 0


def test_nl_query_unsupported_question(client, populated_db):
    """Verify non-support questions return a clean explanation without hallucinations."""
    response = client.post("/api/query", json={"question": "What is the capital of France?"})
    assert response.status_code == 200
    data = response.json()
    assert "status" in data["metadata"]


def test_nl_query_empty_results_handling(client, populated_db):
    """Verify questions with zero matching records return graceful empty result metadata."""
    response = client.post("/api/query", json={"question": "Show all Critical Billing tickets created in 1999"})
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["total_records_matched"] == 0
    assert len(data["data"]) == 0
