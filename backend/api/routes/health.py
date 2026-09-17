import time
from pathlib import Path
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.config import settings
from backend.core.database import get_db, ping_db
from backend.repositories.ticket_repository import TicketRepository
from backend.schemas.common import ApiResponse

router = APIRouter(tags=["Health"])

START_TIME = time.time()


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint reporting:
    - Application status
    - Database availability
    - Dataset availability & path
    - Number of loaded tickets in database
    - Uptime and environment
    """
    db_connected = ping_db()
    
    # Check dataset file on disk
    dataset_file = settings.dataset_absolute_path
    dataset_exists = dataset_file.exists()
    
    # Query ticket count from SQLite
    ticket_count = 0
    if db_connected:
        try:
            repo = TicketRepository(db)
            ticket_count = repo.count_total()
        except Exception:
            ticket_count = 0

    uptime_seconds = round(time.time() - START_TIME, 2)
    
    is_healthy = db_connected and (ticket_count > 0 or dataset_exists)

    return {
        "status": "healthy" if is_healthy else "degraded",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": uptime_seconds,
        "database": {
            "connected": db_connected,
            "engine": "sqlite",
            "url": settings.DATABASE_URL
        },
        "dataset": {
            "path": str(settings.DATASET_PATH),
            "absolute_path": str(dataset_file),
            "file_exists": dataset_exists,
            "loaded_ticket_count": ticket_count
        }
    }
