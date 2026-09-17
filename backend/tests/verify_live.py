import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi.testclient import TestClient
from backend.main import app
import json

client = TestClient(app)

print("=== 1. HEALTH ===")
r = client.get("/health")
print(r.status_code, json.dumps(r.json(), indent=2))

print("\n=== 2. STATS ===")
r = client.get("/api/stats")
print(r.status_code, json.dumps(r.json(), indent=2))

print("\n=== 3. ANOMALIES (Top 3) ===")
r = client.get("/api/anomalies?limit=3")
data = r.json()
print(r.status_code, "Total Flagged:", data["data"]["total_anomalies_detected"])
print("IQR Stats:", json.dumps(data["data"]["iqr_statistics"], indent=2))
print("Sample Item:", json.dumps(data["data"]["items"][0], indent=2))

print("\n=== 4. THE 5 ASSESSMENT NATURAL LANGUAGE QUERIES ===")
queries = [
    "How many tickets are currently open?",
    "Which agent resolved the most tickets this month?",
    "Show me all Critical tickets not resolved within 12 hours.",
    "What is the average customer rating for Technical category tickets?",
    "Are there any anomalies in resolution times this week?",
]

for q in queries:
    r = client.post("/api/query", json={"question": q})
    res = r.json()
    intent = res["interpretation"]["intent"]
    ans = res["answer"]
    matched = res["metadata"]["total_records_matched"]
    ms = res["metadata"]["execution_time_ms"]
    print(f"\nQ: {q}")
    print(f"Intent: {intent}")
    print(f"Answer: {ans}")
    print(f"Matched records: {matched} | Timing: {ms} ms")
