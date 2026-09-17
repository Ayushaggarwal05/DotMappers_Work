from typing import Generator
from fastapi import Depends
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.services.ticket_service import TicketService
from backend.services.ingestion_service import IngestionService


def get_ticket_service(db: Session = Depends(get_db)) -> TicketService:
    """Dependency provider for TicketService."""
    return TicketService(db)


def get_ingestion_service(db: Session = Depends(get_db)) -> IngestionService:
    """Dependency provider for IngestionService."""
    return IngestionService(db)
