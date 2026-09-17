from enum import Enum
from typing import Generic, TypeVar, Optional, List, Any, Dict
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")

class CategoryEnum(str, Enum):
    BILLING = "Billing"
    TECHNICAL = "Technical"
    GENERAL = "General"


class PriorityEnum(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class StatusEnum(str, Enum):
    OPEN = "Open"
    RESOLVED = "Resolved"
    ESCALATED = "Escalated"


class ApiResponse(BaseModel, Generic[T]):
    """Standard unified API response wrapper."""
    success: bool = True
    data: Optional[T] = None
    message: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated payload wrapper."""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int
