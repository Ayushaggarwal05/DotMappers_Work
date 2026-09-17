from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from backend.models.ticket import Ticket
from backend.query_engine.intent_schema import (
    StructuredIntent, QueryIntentType, MetricType, DimensionType,
    FilterOperator, FilterClause, RelativePeriod, DateRangeSpec
)
from backend.schemas.common import CategoryEnum, PriorityEnum, StatusEnum
from backend.core.exceptions import DataValidationError
from backend.core.logging import logger

VALID_CATEGORIES = {c.value.lower(): c.value for c in CategoryEnum}
VALID_PRIORITIES = {p.value.lower(): p.value for p in PriorityEnum}
VALID_STATUSES = {s.value.lower(): s.value for s in StatusEnum}


class IntentValidator:
    """Validates and normalizes StructuredIntent objects before SQL compilation."""

    def __init__(self, db: Optional[Session] = None):
        self.db = db

    def get_dataset_max_date(self) -> datetime:
        """
        Get the latest created_at date in the dataset to anchor relative dates
        like 'this month' or 'this week' realistically to the dataset context.
        """
        if self.db:
            try:
                max_dt = self.db.execute(select(func.max(Ticket.created_at))).scalar()
                if max_dt:
                    return max_dt
            except Exception:
                pass
        return datetime(2024, 3, 31, 23, 59, 59)

    def resolve_date_range(self, date_range: Optional[DateRangeSpec]) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Compute exact start_date and end_date from relative period or custom range."""
        if not date_range:
            return None, None

        if date_range.start_date or date_range.end_date:
            return date_range.start_date, date_range.end_date

        if not date_range.relative_period:
            return None, None

        anchor = self.get_dataset_max_date()
        period = date_range.relative_period

        if period == RelativePeriod.TODAY:
            start = anchor.replace(hour=0, minute=0, second=0, microsecond=0)
            end = anchor.replace(hour=23, minute=59, second=59, microsecond=999999)
            return start, end
        elif period == RelativePeriod.YESTERDAY:
            prev = anchor - timedelta(days=1)
            start = prev.replace(hour=0, minute=0, second=0, microsecond=0)
            end = prev.replace(hour=23, minute=59, second=59, microsecond=999999)
            return start, end
        elif period == RelativePeriod.THIS_WEEK:
            # Week starting Monday of the anchor date's week
            start = (anchor - timedelta(days=anchor.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            end = (start + timedelta(days=6)).replace(hour=23, minute=59, second=59, microsecond=999999)
            return start, end
        elif period == RelativePeriod.LAST_WEEK:
            start = (anchor - timedelta(days=anchor.weekday() + 7)).replace(hour=0, minute=0, second=0, microsecond=0)
            end = (start + timedelta(days=6)).replace(hour=23, minute=59, second=59, microsecond=999999)
            return start, end
        elif period == RelativePeriod.THIS_MONTH:
            start = anchor.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # End of month
            if anchor.month == 12:
                next_month = anchor.replace(year=anchor.year + 1, month=1, day=1)
            else:
                next_month = anchor.replace(month=anchor.month + 1, day=1)
            end = (next_month - timedelta(seconds=1))
            return start, end
        elif period == RelativePeriod.LAST_MONTH:
            if anchor.month == 1:
                last_m_year = anchor.year - 1
                last_m = 12
            else:
                last_m_year = anchor.year
                last_m = anchor.month - 1
            start = datetime(last_m_year, last_m, 1, 0, 0, 0)
            cur_m_start = anchor.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = cur_m_start - timedelta(seconds=1)
            return start, end
        elif period == RelativePeriod.OLDER_THAN_24H:
            end = anchor - timedelta(hours=24)
            return None, end

        return None, None

    def normalize_filter_value(self, clause: FilterClause) -> FilterClause:
        """Normalize enum-like filter values (e.g. 'technical' -> 'Technical')."""
        field = clause.field.lower()
        val = clause.value

        if field == "category":
            if isinstance(val, str):
                normalized = VALID_CATEGORIES.get(val.strip().lower())
                if normalized:
                    clause.value = normalized
            elif isinstance(val, list):
                clause.value = [VALID_CATEGORIES.get(str(x).strip().lower(), str(x)) for x in val]

        elif field == "priority":
            if isinstance(val, str):
                normalized = VALID_PRIORITIES.get(val.strip().lower())
                if normalized:
                    clause.value = normalized
            elif isinstance(val, list):
                clause.value = [VALID_PRIORITIES.get(str(x).strip().lower(), str(x)) for x in val]

        elif field == "status":
            if isinstance(val, str):
                normalized = VALID_STATUSES.get(val.strip().lower())
                if normalized:
                    clause.value = normalized
            elif isinstance(val, list):
                clause.value = [VALID_STATUSES.get(str(x).strip().lower(), str(x)) for x in val]

        elif field in ("response_time_hrs", "resolution_time_hrs", "customer_rating"):
            if val is not None and not isinstance(val, (int, float)):
                try:
                    clause.value = float(val) if field != "customer_rating" else int(float(val))
                except (ValueError, TypeError):
                    pass

        return clause

    def validate_and_normalize(self, intent: StructuredIntent) -> StructuredIntent:
        """Full validation and normalization pipeline for incoming intent."""
        if intent.intent == QueryIntentType.UNSUPPORTED:
            return intent

        # 1. Normalize all filters
        normalized_filters = []
        for clause in intent.filters:
            norm_clause = self.normalize_filter_value(clause)
            normalized_filters.append(norm_clause)
        intent.filters = normalized_filters

        # 2. Resolve relative dates into concrete timestamps if needed
        if intent.date_range and intent.date_range.relative_period:
            start_dt, end_dt = self.resolve_date_range(intent.date_range)
            if start_dt or end_dt:
                intent.date_range.start_date = start_dt
                intent.date_range.end_date = end_dt

        # 3. If sorting is requested without explicit sort field, set reasonable default
        if intent.intent == QueryIntentType.TOP_N and not intent.sort:
            first_metric = intent.metrics[0].value if intent.metrics else "count"
            from backend.query_engine.intent_schema import SortSpec, SortOrder
            intent.sort = SortSpec(field=first_metric, order=SortOrder.DESC)

        return intent
