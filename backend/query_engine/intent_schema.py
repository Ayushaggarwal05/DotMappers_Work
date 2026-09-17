from enum import Enum
from typing import List, Optional, Any, Dict, Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator


class QueryIntentType(str, Enum):
    """Supported analytical intentions."""
    COUNT = "count"
    FILTER = "filter"
    AGGREGATION = "aggregation"
    GROUP_BY = "group_by"
    TOP_N = "top_n"
    COMPARISON = "comparison"
    ANOMALY_DETECTION = "anomaly_detection"
    UNSUPPORTED = "unsupported"


class MetricType(str, Enum):
    """Allowed deterministic metric aggregations."""
    COUNT = "count"
    AVG_RESPONSE_TIME = "avg_response_time"
    AVG_RESOLUTION_TIME = "avg_resolution_time"
    AVG_RATING = "avg_rating"
    RESOLUTION_RATE = "resolution_rate"
    ESCALATION_RATE = "escalation_rate"
    SLA_BREACH_COUNT = "sla_breach_count"
    MIN_RESPONSE_TIME = "min_response_time"
    MAX_RESPONSE_TIME = "max_response_time"
    MIN_RESOLUTION_TIME = "min_resolution_time"
    MAX_RESOLUTION_TIME = "max_resolution_time"


class DimensionType(str, Enum):
    """Allowed grouping dimensions."""
    CATEGORY = "category"
    PRIORITY = "priority"
    STATUS = "status"
    AGENT_ID = "agent_id"
    MONTH = "month"
    WEEK = "week"
    DATE = "date"


class FilterOperator(str, Enum):
    """Allowed comparison operators."""
    EQ = "eq"          # =
    NEQ = "neq"        # !=
    IN = "in"          # IN (...)
    NOT_IN = "not_in"  # NOT IN (...)
    GT = "gt"          # >
    GTE = "gte"        # >=
    LT = "lt"          # <
    LTE = "lte"        # <=
    LIKE = "like"      # ILIKE / contains
    IS_NULL = "is_null"# IS NULL
    NOT_NULL = "not_null" # IS NOT NULL


class FilterClause(BaseModel):
    """Strict parameterized filter condition."""
    field: str = Field(..., description="Target column in tickets table")
    operator: FilterOperator = Field(FilterOperator.EQ, description="Comparison operator")
    value: Optional[Union[str, int, float, List[Union[str, int, float]]]] = Field(
        None, description="Literal comparison value"
    )

    @field_validator("field")
    @classmethod
    def validate_field(cls, v: str) -> str:
        allowed = {
            "ticket_id", "created_at", "category", "priority", "status",
            "response_time_hrs", "resolution_time_hrs", "agent_id",
            "customer_rating", "issue_summary"
        }
        clean = v.strip().lower()
        if clean not in allowed:
            raise ValueError(f"Invalid filter field '{v}'. Allowed fields: {allowed}")
        return clean


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class SortSpec(BaseModel):
    """Sort criteria."""
    field: str = Field(..., description="Column or metric to sort by")
    order: SortOrder = Field(SortOrder.DESC, description="Direction (asc or desc)")


class RelativePeriod(str, Enum):
    """Common relative date filters."""
    TODAY = "today"
    YESTERDAY = "yesterday"
    THIS_WEEK = "this_week"
    LAST_WEEK = "last_week"
    THIS_MONTH = "this_month"
    LAST_MONTH = "last_month"
    OLDER_THAN_24H = "older_than_24h"
    CUSTOM = "custom"


class DateRangeSpec(BaseModel):
    """Date window specifications."""
    relative_period: Optional[RelativePeriod] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class StructuredIntent(BaseModel):
    """
    STRICT Pydantic intent schema produced by LLM and validated before query execution.
    
    Guarantees:
    - Zero SQL execution by LLM
    - Strictly typed metrics and allowlisted columns
    - Clean parameterization
    """
    intent: QueryIntentType = Field(..., description="Primary analytical intent")
    metrics: List[MetricType] = Field(
        default_factory=lambda: [MetricType.COUNT],
        description="Aggregation metrics"
    )
    group_by: List[DimensionType] = Field(
        default_factory=list,
        description="Dimensions to group by"
    )
    filters: List[FilterClause] = Field(
        default_factory=list,
        description="Filter predicates"
    )
    date_range: Optional[DateRangeSpec] = None
    sort: Optional[SortSpec] = None
    limit: Optional[int] = Field(100, ge=1, le=1000, description="Max rows returned")
    anomaly_request: bool = Field(False, description="True if question pertains to anomaly detection")
    unresolved_only: bool = Field(False, description="True if query specifically targets unresolved tickets")
    raw_question: str = Field("", description="Original user prompt")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="LLM confidence score")
    notes: Optional[str] = Field(None, description="Explanation or reasoning from intent interpretation")

    @model_validator(mode="after")
    def validate_consistency(self):
        # If anomaly detection is requested, ensure intent flag is synced
        if self.intent == QueryIntentType.ANOMALY_DETECTION:
            self.anomaly_request = True
        elif self.anomaly_request:
            self.intent = QueryIntentType.ANOMALY_DETECTION

        # If unresolved_only flag is set, ensure we have filter for unresolved if not already present
        if self.unresolved_only:
            has_status_filter = any(f.field == "status" for f in self.filters)
            has_res_time_filter = any(f.field == "resolution_time_hrs" for f in self.filters)
            if not (has_status_filter or has_res_time_filter):
                self.filters.append(
                    FilterClause(
                        field="status",
                        operator=FilterOperator.IN,
                        value=["Open", "Escalated"]
                    )
                )
        return self
