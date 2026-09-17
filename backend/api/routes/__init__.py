from backend.api.routes.health import router as health_router
from backend.api.routes.tickets import router as tickets_router
from backend.api.routes.query import router as query_router
from backend.api.routes.anomalies import router as anomalies_router
from backend.api.routes.stats import router as stats_router

__all__ = [
    "health_router",
    "tickets_router",
    "query_router",
    "anomalies_router",
    "stats_router",
]
