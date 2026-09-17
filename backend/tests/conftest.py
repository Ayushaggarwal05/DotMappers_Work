import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.core.database import Base, get_db
from backend.models.ticket import Ticket
from backend.services.ingestion_service import IngestionService
from backend.main import create_app
from backend.config import settings

# Use an in-memory SQLite database for test isolation
TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="session")
def engine():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(engine):
    """Provide a clean transactional session for each test."""
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient with overridden database dependency."""
    app = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def populated_db(db_session):
    """Database pre-populated with actual support_tickets.csv."""
    ingestion = IngestionService(db_session)
    csv_path = settings.dataset_absolute_path
    if csv_path.exists():
        ingestion.ingest_from_file(csv_path)
    return db_session
