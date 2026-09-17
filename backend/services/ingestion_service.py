import csv
import io
import os
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

from sqlalchemy.orm import Session

from backend.config import settings
from backend.core.logging import logger
from backend.core.exceptions import DatasetNotFoundError, IngestionError, DataValidationError
from backend.models.ticket import Ticket
from backend.repositories.ticket_repository import TicketRepository
from backend.schemas.common import CategoryEnum, PriorityEnum, StatusEnum
from backend.schemas.ticket import IngestionStats


REQUIRED_COLUMNS = {
    "ticket_id",
    "created_at",
    "category",
    "priority",
    "status",
    "response_time_hrs",
    "resolution_time_hrs",
    "agent_id",
    "customer_rating",
    "issue_summary",
}

VALID_CATEGORIES = {c.value for c in CategoryEnum}
VALID_PRIORITIES = {p.value for p in PriorityEnum}
VALID_STATUSES = {s.value for s in StatusEnum}


class IngestionService:
    """Service for validating, normalizing, and ingesting support ticket datasets."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = TicketRepository(db)

    def parse_datetime(self, val: str) -> datetime:
        """Parse various ISO and custom datetime formats."""
        val = val.strip()
        formats = [
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(val, fmt)
            except ValueError:
                continue
        raise ValueError(f"Unable to parse timestamp '{val}'")

    def clean_nullable_float(self, val: Any) -> Optional[float]:
        """Convert empty/null representations to Optional[float]."""
        if val is None:
            return None
        s = str(val).strip()
        if not s or s.lower() in ("null", "none", "nan", "na", ""):
            return None
        return float(s)

    def clean_nullable_int(self, val: Any) -> Optional[int]:
        """Convert empty/null representations to Optional[int]."""
        if val is None:
            return None
        s = str(val).strip()
        if not s or s.lower() in ("null", "none", "nan", "na", ""):
            return None
        return int(float(s))

    def validate_and_normalize_row(self, row: Dict[str, Any], row_num: int) -> Dict[str, Any]:
        """
        Validate and clean a single raw row dictionary from CSV.
        Raises ValueError if required constraints fail.
        """
        # 1. Check ticket_id
        ticket_id = str(row.get("ticket_id", "")).strip()
        if not ticket_id:
            raise ValueError(f"Row {row_num}: 'ticket_id' is missing or empty")

        # 2. Check created_at
        created_at_raw = str(row.get("created_at", "")).strip()
        if not created_at_raw:
            raise ValueError(f"Row {row_num}: 'created_at' is required")
        created_at = self.parse_datetime(created_at_raw)

        # 3. Category
        category = str(row.get("category", "")).strip()
        if category not in VALID_CATEGORIES:
            raise ValueError(f"Row {row_num}: Invalid category '{category}'. Must be one of {VALID_CATEGORIES}")

        # 4. Priority
        priority = str(row.get("priority", "")).strip()
        if priority not in VALID_PRIORITIES:
            raise ValueError(f"Row {row_num}: Invalid priority '{priority}'. Must be one of {VALID_PRIORITIES}")

        # 5. Status
        status = str(row.get("status", "")).strip()
        if status not in VALID_STATUSES:
            raise ValueError(f"Row {row_num}: Invalid status '{status}'. Must be one of {VALID_STATUSES}")

        # 6. Response time
        response_time_raw = row.get("response_time_hrs")
        try:
            response_time_hrs = float(str(response_time_raw).strip())
            if response_time_hrs < 0:
                raise ValueError("Response time cannot be negative")
        except Exception as e:
            raise ValueError(f"Row {row_num}: Invalid response_time_hrs '{response_time_raw}': {e}")

        # 7. Resolution time
        resolution_time_hrs = self.clean_nullable_float(row.get("resolution_time_hrs"))
        if resolution_time_hrs is not None and resolution_time_hrs < 0:
            raise ValueError(f"Row {row_num}: Resolution time cannot be negative")

        # 8. Agent ID
        agent_id = str(row.get("agent_id", "")).strip()
        if not agent_id:
            raise ValueError(f"Row {row_num}: 'agent_id' is missing")

        # 9. Customer Rating (1-5, nullable)
        customer_rating = self.clean_nullable_int(row.get("customer_rating"))
        if customer_rating is not None and not (1 <= customer_rating <= 5):
            raise ValueError(f"Row {row_num}: 'customer_rating' must be between 1 and 5 (got {customer_rating})")

        # 10. Issue Summary
        issue_summary = str(row.get("issue_summary", "")).strip()
        if not issue_summary:
            raise ValueError(f"Row {row_num}: 'issue_summary' is required")

        return {
            "ticket_id": ticket_id,
            "created_at": created_at,
            "category": category,
            "priority": priority,
            "status": status,
            "response_time_hrs": response_time_hrs,
            "resolution_time_hrs": resolution_time_hrs,
            "agent_id": agent_id,
            "customer_rating": customer_rating,
            "issue_summary": issue_summary,
        }

    def ingest_from_file(self, file_path: Optional[Union[str, Path]] = None) -> IngestionStats:
        """
        Ingest tickets from a CSV file path.
        Defaults to settings.dataset_absolute_path if not provided.
        """
        target_path = Path(file_path) if file_path else settings.dataset_absolute_path
        
        logger.info(f"Initiating dataset ingestion from: {target_path}")
        if not target_path.exists():
            logger.error(f"Dataset file does not exist: {target_path}")
            raise DatasetNotFoundError(str(target_path))

        with open(target_path, mode="r", encoding="utf-8-sig") as f:
            return self.ingest_from_csv_stream(f)

    def ingest_from_csv_stream(self, stream: io.TextIOBase) -> IngestionStats:
        """
        Ingest tickets from an open text stream/string buffer.
        """
        start_time = time.perf_counter()
        reader = csv.DictReader(stream)

        if not reader.fieldnames:
            raise IngestionError("CSV file is empty or headers are missing")

        # Check required columns
        headers = set(col.strip() for col in reader.fieldnames if col)
        missing_columns = REQUIRED_COLUMNS - headers
        if missing_columns:
            raise IngestionError(
                f"Missing required columns in CSV: {missing_columns}",
                details={"missing_columns": list(missing_columns), "found_columns": list(headers)}
            )

        valid_records = []
        errors = []
        total_processed = 0
        skipped = 0

        for row_num, raw_row in enumerate(reader, start=2):  # line 2 is first data row
            total_processed += 1
            try:
                cleaned = self.validate_and_normalize_row(raw_row, row_num)
                valid_records.append(cleaned)
            except Exception as e:
                skipped += 1
                msg = f"Skipping row {row_num}: {e}"
                errors.append(msg)
                logger.warning(msg)

        logger.info(f"Validated {len(valid_records)} rows ({skipped} skipped). Inserting into database...")
        
        inserted, updated = self.repository.bulk_upsert(valid_records)
        elapsed = time.perf_counter() - start_time

        logger.info(
            f"Ingestion completed in {elapsed:.3f}s: {inserted} inserted, {updated} updated, {skipped} skipped."
        )

        return IngestionStats(
            total_processed=total_processed,
            inserted_count=inserted,
            updated_count=updated,
            skipped_count=skipped,
            errors=errors[:50],  # cap returned errors
            duration_seconds=round(elapsed, 3)
        )
