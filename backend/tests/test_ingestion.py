import io
import pytest
from backend.services.ingestion_service import IngestionService
from backend.repositories.ticket_repository import TicketRepository
from backend.core.exceptions import DatasetNotFoundError, IngestionError


def test_ingest_actual_dataset(db_session):
    """Test full ingestion of the 500-row support_tickets.csv."""
    ingestion = IngestionService(db_session)
    stats = ingestion.ingest_from_file()

    assert stats.total_processed == 500
    assert stats.inserted_count == 500
    assert stats.skipped_count == 0
    assert len(stats.errors) == 0

    repo = TicketRepository(db_session)
    assert repo.count_total() == 500


def test_ingest_csv_stream_with_nulls_and_formats(db_session):
    """Test CSV ingestion handling of null resolution times and ratings."""
    csv_data = (
        "ticket_id,created_at,category,priority,status,response_time_hrs,resolution_time_hrs,agent_id,customer_rating,issue_summary\n"
        "TEST-001,2024-03-01 10:00,Billing,High,Resolved,1.5,4.2,AGT-01,5,Sample billing issue\n"
        "TEST-002,2024-03-02 11:30,Technical,Low,Open,2.0,,AGT-02,,Sample open ticket with nulls\n"
    )
    
    stream = io.StringIO(csv_data)
    ingestion = IngestionService(db_session)
    stats = ingestion.ingest_from_csv_stream(stream)

    assert stats.total_processed == 2
    assert stats.inserted_count == 2
    assert stats.skipped_count == 0

    repo = TicketRepository(db_session)
    t1 = repo.get_by_id("TEST-001")
    assert t1 is not None
    assert t1.customer_rating == 5
    assert t1.resolution_time_hrs == 4.2

    t2 = repo.get_by_id("TEST-002")
    assert t2 is not None
    assert t2.resolution_time_hrs is None
    assert t2.customer_rating is None
    assert t2.status == "Open"


def test_ingest_malformed_rows_skipped_gracefully(db_session):
    """Ensure malformed or invalid enum rows are skipped with logged errors."""
    csv_data = (
        "ticket_id,created_at,category,priority,status,response_time_hrs,resolution_time_hrs,agent_id,customer_rating,issue_summary\n"
        "VALID-001,2024-03-01 10:00,Billing,High,Resolved,1.5,4.2,AGT-01,5,Valid ticket\n"
        "INVALID-002,2024-03-02 11:30,UnknownCategory,Low,Open,2.0,,,AGT-02,,Invalid category\n"
        "INVALID-003,invalid-date,Technical,Low,Open,2.0,,,AGT-02,,Invalid date\n"
    )
    
    stream = io.StringIO(csv_data)
    ingestion = IngestionService(db_session)
    stats = ingestion.ingest_from_csv_stream(stream)

    assert stats.total_processed == 3
    assert stats.inserted_count == 1
    assert stats.skipped_count == 2
    assert len(stats.errors) == 2


def test_ingestion_missing_columns_raises_error(db_session):
    """Ensure missing columns in CSV header raise IngestionError."""
    csv_data = "ticket_id,created_at,category\nTEST-001,2024-01-01 10:00,Billing\n"
    stream = io.StringIO(csv_data)
    ingestion = IngestionService(db_session)
    
    with pytest.raises(IngestionError):
        ingestion.ingest_from_csv_stream(stream)
