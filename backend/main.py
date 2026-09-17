from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.core.database import init_db, SessionLocal
from backend.core.logging import setup_logging, logger
from backend.core.exceptions import (
    AppException, app_exception_handler, unhandled_exception_handler
)
from backend.services.ingestion_service import IngestionService
from backend.api.routes.health import router as health_router
from backend.api.routes.tickets import router as tickets_router
from backend.api.routes.query import router as query_router
from backend.api.routes.anomalies import router as anomalies_router
from backend.api.routes.stats import router as stats_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown hooks."""
    # 1. Initialize logging
    setup_logging()
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} ({settings.ENVIRONMENT})")

    # 2. Initialize Database Schema
    init_db()

    # 3. Auto-ingest dataset on startup if configured
    if settings.AUTO_INGEST_ON_STARTUP:
        db = SessionLocal()
        try:
            ingestion = IngestionService(db)
            if settings.dataset_absolute_path.exists():
                logger.info(f"Auto-ingesting dataset from: {settings.dataset_absolute_path}")
                stats = ingestion.ingest_from_file()
                logger.info(
                    f"Startup ingestion finished: {stats.inserted_count} inserted, "
                    f"{stats.updated_count} updated ({stats.total_processed} total processed)"
                )
            else:
                logger.warning(f"Dataset file not found at startup: {settings.dataset_absolute_path}")
        except Exception as e:
            logger.error(f"Startup ingestion error: {e}")
        finally:
            db.close()

    yield

    logger.info(f"Shutting down {settings.APP_NAME}...")


def create_app() -> FastAPI:
    """Factory function for FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Production-quality AI Customer Support Analytics Backend & Query Engine",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS if settings.CORS_ORIGINS else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Global Exception Handlers
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Root endpoints
    app.include_router(health_router)
    app.include_router(query_router)
    app.include_router(tickets_router)
    app.include_router(anomalies_router)
    app.include_router(stats_router)

    # /api endpoints
    app.include_router(health_router, prefix="/api")
    app.include_router(query_router, prefix="/api")
    app.include_router(tickets_router, prefix="/api")
    app.include_router(anomalies_router, prefix="/api")
    app.include_router(stats_router, prefix="/api")

    # /api/v1 endpoints
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(query_router, prefix="/api/v1")
    app.include_router(tickets_router, prefix="/api/v1")
    app.include_router(anomalies_router, prefix="/api/v1")
    app.include_router(stats_router, prefix="/api/v1")

    return app


app = create_app()
