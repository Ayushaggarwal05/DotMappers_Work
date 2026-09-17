import os
import requests
from typing import Dict, Any, Optional, List


class ApiClientError(Exception):
    """Custom error class for frontend API communication issues."""
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class ApiClient:
    """Production-quality HTTP client for communicating with the TracePath AI FastAPI backend."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 12.0):
        self.base_url = (base_url or os.getenv("API_BASE_URL", "http://localhost:8000")).rstrip("/")
        self.timeout = timeout

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
            else:
                error_body = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
                raise ApiClientError(
                    message=f"API Error ({resp.status_code}): {error_body.get('error', {}).get('message', resp.text)}",
                    status_code=resp.status_code,
                    details=error_body
                )
        except requests.exceptions.ConnectionError:
            raise ApiClientError(
                message=f"Cannot connect to TracePath Backend at {self.base_url}. Ensure the server is running (`python main.py`)."
            )
        except requests.exceptions.Timeout:
            raise ApiClientError(
                message=f"Backend request timed out after {self.timeout}s."
            )
        except ApiClientError:
            raise
        except Exception as e:
            raise ApiClientError(f"Unexpected network error: {str(e)}")

    def _post(self, endpoint: str, json_data: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        try:
            resp = requests.post(url, json=json_data, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
            else:
                error_body = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
                raise ApiClientError(
                    message=f"API Error ({resp.status_code}): {error_body.get('error', {}).get('message', resp.text)}",
                    status_code=resp.status_code,
                    details=error_body
                )
        except requests.exceptions.ConnectionError:
            raise ApiClientError(
                message=f"Cannot connect to TracePath Backend at {self.base_url}. Ensure the server is running (`python main.py`)."
            )
        except requests.exceptions.Timeout:
            raise ApiClientError(
                message=f"Backend request timed out after {self.timeout}s."
            )
        except ApiClientError:
            raise
        except Exception as e:
            raise ApiClientError(f"Unexpected network error: {str(e)}")

    # ================= Endpoints =================

    def get_health(self) -> Dict[str, Any]:
        """Fetch health & system diagnostic info."""
        return self._get("/health")

    def get_stats(self) -> Dict[str, Any]:
        """Fetch dashboard KPI metrics."""
        return self._get("/api/stats")

    def get_stats_breakdown(self) -> Dict[str, Any]:
        """Fetch chart breakdown datasets."""
        return self._get("/api/stats/breakdown")

    def get_anomalies(
        self,
        anomaly_type: Optional[str] = None,
        severity: Optional[str] = None,
        priority: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """Fetch detected anomalies & statistical IQR baselines."""
        params: Dict[str, Any] = {"limit": limit}
        if anomaly_type:
            params["anomaly_type"] = anomaly_type
        if severity:
            params["severity"] = severity
        if priority:
            params["priority"] = priority
        if category:
            params["category"] = category
        return self._get("/api/anomalies", params=params)

    def get_tickets(
        self,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        status: Optional[str] = None,
        agent_id: Optional[str] = None,
        search: Optional[str] = None,
        min_rating: Optional[int] = None,
        max_rating: Optional[int] = None,
        page: int = 1,
        page_size: int = 25
    ) -> Dict[str, Any]:
        """Fetch paginated ticket records."""
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        if category and category != "All":
            params["category"] = category
        if priority and priority != "All":
            params["priority"] = priority
        if status and status != "All":
            params["status"] = status
        if agent_id and agent_id != "All":
            params["agent_id"] = agent_id
        if search:
            params["search"] = search
        if min_rating:
            params["min_rating"] = min_rating
        if max_rating:
            params["max_rating"] = max_rating
        return self._get("/api/tickets", params=params)

    def get_ticket_by_id(self, ticket_id: str) -> Dict[str, Any]:
        """Fetch single ticket detail."""
        return self._get(f"/api/tickets/{ticket_id}")

    def query_natural_language(self, question: str) -> Dict[str, Any]:
        """Send natural language query to the AI engine."""
        return self._post("/api/query", json_data={"question": question})
