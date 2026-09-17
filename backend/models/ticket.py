from sqlalchemy import Column, String, Float, Integer, DateTime, Text, Index
from backend.core.database import Base


class Ticket(Base):
    """SQLAlchemy model for customer support tickets."""
    __tablename__ = "tickets"

    ticket_id = Column(String(50), primary_key=True, index=True)
    created_at = Column(DateTime, nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)
    priority = Column(String(50), nullable=False, index=True)
    status = Column(String(50), nullable=False, index=True)
    response_time_hrs = Column(Float, nullable=False)
    resolution_time_hrs = Column(Float, nullable=True)
    agent_id = Column(String(50), nullable=False, index=True)
    customer_rating = Column(Integer, nullable=True)
    issue_summary = Column(Text, nullable=False)

    __table_args__ = (
        Index("ix_tickets_category_status", "category", "status"),
        Index("ix_tickets_priority_status", "priority", "status"),
        Index("ix_tickets_agent_created", "agent_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Ticket(id={self.ticket_id}, status={self.status}, category={self.category}, priority={self.priority})>"
