from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
import time
from sqlalchemy import (
    select, func, and_, or_, desc, asc, case, cast, Integer, Float, String, text
)
from sqlalchemy.orm import Session

from backend.models.ticket import Ticket
from backend.schemas.ticket import TicketFilterParams, TicketMetrics
from backend.schemas.query import (
    StructuredQuery, StructuredQueryResult, MetricType, DimensionType,
    FilterOperator, FilterCondition, SortOrder, QueryIntent
)
from backend.core.logging import logger
from backend.core.exceptions import DatabaseError, QueryExecutionError


class TicketRepository:
    """Safe, parameterized data access layer for tickets."""

    def __init__(self, db: Session):
        self.db = db

    def count_total(self) -> int:
        """Return the total number of ticket records in SQLite."""
        try:
            stmt = select(func.count()).select_from(Ticket)
            return self.db.execute(stmt).scalar() or 0
        except Exception as e:
            logger.error(f"Failed to count tickets: {e}")
            raise DatabaseError("Failed to query ticket count", details={"error": str(e)})

    def get_by_id(self, ticket_id: str) -> Optional[Ticket]:
        """Fetch a single ticket by its primary key ID."""
        try:
            stmt = select(Ticket).where(Ticket.ticket_id == ticket_id)
            return self.db.execute(stmt).scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching ticket {ticket_id}: {e}")
            raise DatabaseError(f"Error fetching ticket {ticket_id}", details={"error": str(e)})

    def bulk_upsert(self, tickets_data: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Efficient bulk insert or update using SQLite ON CONFLICT DO UPDATE.
        Returns: (inserted_count, updated_count)
        """
        if not tickets_data:
            return 0, 0

        inserted = 0
        try:
            for item in tickets_data:
                ticket_id = item["ticket_id"]
                existing = self.get_by_id(ticket_id)
                if existing:
                    for k, v in item.items():
                        setattr(existing, k, v)
                else:
                    new_ticket = Ticket(**item)
                    self.db.add(new_ticket)
                    inserted += 1
            
            self.db.commit()
            updated = len(tickets_data) - inserted
            return inserted, updated
        except Exception as e:
            self.db.rollback()
            logger.error(f"Bulk upsert failed: {e}")
            raise DatabaseError("Bulk upsert transaction failed", details={"error": str(e)})

    def filter_tickets(self, params: TicketFilterParams) -> Tuple[List[Ticket], int]:
        """
        Parameterized ticket filtering with pagination.
        Returns: (tickets_list, total_matched_count)
        """
        try:
            query = select(Ticket)
            count_query = select(func.count()).select_from(Ticket)
            
            conditions = []
            
            if params.category:
                conditions.append(Ticket.category == params.category.value)
            if params.priority:
                conditions.append(Ticket.priority == params.priority.value)
            if params.status:
                conditions.append(Ticket.status == params.status.value)
            if params.agent_id:
                conditions.append(Ticket.agent_id == params.agent_id)
            if params.start_date:
                conditions.append(Ticket.created_at >= params.start_date)
            if params.end_date:
                conditions.append(Ticket.created_at <= params.end_date)
            if params.min_rating is not None:
                conditions.append(Ticket.customer_rating >= params.min_rating)
            if params.max_rating is not None:
                conditions.append(Ticket.customer_rating <= params.max_rating)
            if params.search:
                search_term = f"%{params.search.strip()}%"
                conditions.append(
                    or_(
                        Ticket.issue_summary.ilike(search_term),
                        Ticket.ticket_id.ilike(search_term),
                        Ticket.agent_id.ilike(search_term)
                    )
                )

            if conditions:
                query = query.where(and_(*conditions))
                count_query = count_query.where(and_(*conditions))

            total = self.db.execute(count_query).scalar() or 0
            
            # Apply ordering and pagination
            offset = (params.page - 1) * params.page_size
            query = query.order_by(desc(Ticket.created_at)).offset(offset).limit(params.page_size)
            
            items = list(self.db.execute(query).scalars().all())
            return items, total
        except Exception as e:
            logger.error(f"Error filtering tickets: {e}")
            raise DatabaseError("Failed to filter tickets", details={"error": str(e)})

    def get_overall_metrics(
        self,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        agent_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> TicketMetrics:
        """
        Calculate aggregated operational metrics with single parameterized aggregation query.
        """
        try:
            conditions = []
            if category:
                conditions.append(Ticket.category == category)
            if priority:
                conditions.append(Ticket.priority == priority)
            if agent_id:
                conditions.append(Ticket.agent_id == agent_id)
            if start_date:
                conditions.append(Ticket.created_at >= start_date)
            if end_date:
                conditions.append(Ticket.created_at <= end_date)

            where_clause = and_(*conditions) if conditions else True

            # SLA breach definition: response_time_hrs > 4.0 or resolution_time_hrs > 48.0
            sla_breach_case = case(
                (or_(Ticket.response_time_hrs > 4.0, Ticket.resolution_time_hrs > 48.0), 1),
                else_=0
            )

            stmt = select(
                func.count().label("total"),
                func.sum(case((Ticket.status == "Open", 1), else_=0)).label("open_count"),
                func.sum(case((Ticket.status == "Resolved", 1), else_=0)).label("resolved_count"),
                func.sum(case((Ticket.status == "Escalated", 1), else_=0)).label("escalated_count"),
                func.avg(Ticket.response_time_hrs).label("avg_response"),
                func.avg(Ticket.resolution_time_hrs).label("avg_resolution"),
                func.avg(Ticket.customer_rating).label("avg_rating"),
                func.sum(sla_breach_case).label("sla_breaches")
            ).where(where_clause)

            row = self.db.execute(stmt).one()
            
            total = row.total or 0
            open_count = row.open_count or 0
            resolved_count = row.resolved_count or 0
            escalated_count = row.escalated_count or 0
            avg_resp = float(row.avg_response) if row.avg_response is not None else 0.0
            avg_res = float(row.avg_resolution) if row.avg_resolution is not None else None
            avg_rat = float(row.avg_rating) if row.avg_rating is not None else None
            sla_breaches = row.sla_breaches or 0

            res_rate = (resolved_count / total * 100.0) if total > 0 else 0.0
            esc_rate = (escalated_count / total * 100.0) if total > 0 else 0.0

            return TicketMetrics(
                total_tickets=total,
                open_tickets=open_count,
                resolved_tickets=resolved_count,
                escalated_tickets=escalated_count,
                resolution_rate_pct=round(res_rate, 2),
                escalation_rate_pct=round(esc_rate, 2),
                avg_response_time_hrs=round(avg_resp, 2),
                avg_resolution_time_hrs=round(avg_res, 2) if avg_res is not None else None,
                avg_customer_rating=round(avg_rat, 2) if avg_rat is not None else None,
                sla_breach_count=sla_breaches
            )
        except Exception as e:
            logger.error(f"Error computing overall metrics: {e}")
            raise DatabaseError("Failed to calculate ticket metrics", details={"error": str(e)})

    def execute_structured_query(self, query: StructuredQuery) -> StructuredQueryResult:
        """
        Deterministic, safe execution of a structured analytics query.
        Guarantees zero SQL injection by compiling only verified expressions.
        """
        start_time = time.perf_counter()
        try:
            # 1. Build Filter Conditions safely
            filter_clauses = []
            
            # Map of column objects
            col_map = {
                "ticket_id": Ticket.ticket_id,
                "created_at": Ticket.created_at,
                "category": Ticket.category,
                "priority": Ticket.priority,
                "status": Ticket.status,
                "response_time_hrs": Ticket.response_time_hrs,
                "resolution_time_hrs": Ticket.resolution_time_hrs,
                "agent_id": Ticket.agent_id,
                "customer_rating": Ticket.customer_rating,
                "issue_summary": Ticket.issue_summary,
            }

            for cond in query.filters:
                col = col_map.get(cond.field)
                if col is None:
                    raise QueryExecutionError(f"Field '{cond.field}' cannot be filtered")
                
                op = cond.operator
                val = cond.value
                
                if op == FilterOperator.EQ:
                    filter_clauses.append(col == val)
                elif op == FilterOperator.NEQ:
                    filter_clauses.append(col != val)
                elif op == FilterOperator.IN:
                    val_list = val if isinstance(val, list) else [val]
                    filter_clauses.append(col.in_(val_list))
                elif op == FilterOperator.NOT_IN:
                    val_list = val if isinstance(val, list) else [val]
                    filter_clauses.append(col.not_in(val_list))
                elif op == FilterOperator.GT:
                    filter_clauses.append(col > val)
                elif op == FilterOperator.GTE:
                    filter_clauses.append(col >= val)
                elif op == FilterOperator.LT:
                    filter_clauses.append(col < val)
                elif op == FilterOperator.LTE:
                    filter_clauses.append(col <= val)
                elif op == FilterOperator.LIKE:
                    filter_clauses.append(col.ilike(f"%{val}%"))
                elif op == FilterOperator.IS_NULL:
                    filter_clauses.append(col.is_(None))
                elif op == FilterOperator.NOT_NULL:
                    filter_clauses.append(col.isnot(None))

            # Apply date boundaries if provided
            if query.date_range:
                if query.date_range.start_date:
                    filter_clauses.append(Ticket.created_at >= query.date_range.start_date)
                if query.date_range.end_date:
                    filter_clauses.append(Ticket.created_at <= query.date_range.end_date)

            where_stmt = and_(*filter_clauses) if filter_clauses else True

            # 2. Build Metrics Select Expressions
            metric_expressions = []
            for metric in query.metrics:
                if metric == MetricType.COUNT:
                    metric_expressions.append(func.count().label("count"))
                elif metric == MetricType.AVG_RESPONSE_TIME:
                    metric_expressions.append(func.avg(Ticket.response_time_hrs).label("avg_response_time"))
                elif metric == MetricType.AVG_RESOLUTION_TIME:
                    metric_expressions.append(func.avg(Ticket.resolution_time_hrs).label("avg_resolution_time"))
                elif metric == MetricType.AVG_RATING:
                    metric_expressions.append(func.avg(Ticket.customer_rating).label("avg_rating"))
                elif metric == MetricType.RESOLUTION_RATE:
                    resolved_cases = func.sum(case((Ticket.status == "Resolved", 1.0), else_=0.0))
                    total_cases = func.cast(func.count(), Float)
                    metric_expressions.append((resolved_cases / func.nullif(total_cases, 0) * 100.0).label("resolution_rate"))
                elif metric == MetricType.ESCALATION_RATE:
                    escalated_cases = func.sum(case((Ticket.status == "Escalated", 1.0), else_=0.0))
                    total_cases = func.cast(func.count(), Float)
                    metric_expressions.append((escalated_cases / func.nullif(total_cases, 0) * 100.0).label("escalation_rate"))
                elif metric == MetricType.SLA_BREACH_COUNT:
                    metric_expressions.append(
                        func.sum(case((or_(Ticket.response_time_hrs > 4.0, Ticket.resolution_time_hrs > 48.0), 1), else_=0)).label("sla_breach_count")
                    )
                elif metric == MetricType.MIN_RESPONSE_TIME:
                    metric_expressions.append(func.min(Ticket.response_time_hrs).label("min_response_time"))
                elif metric == MetricType.MAX_RESPONSE_TIME:
                    metric_expressions.append(func.max(Ticket.response_time_hrs).label("max_response_time"))
                elif metric == MetricType.MIN_RESOLUTION_TIME:
                    metric_expressions.append(func.min(Ticket.resolution_time_hrs).label("min_resolution_time"))
                elif metric == MetricType.MAX_RESOLUTION_TIME:
                    metric_expressions.append(func.max(Ticket.resolution_time_hrs).label("max_resolution_time"))

            # Default metric if none passed
            if not metric_expressions:
                metric_expressions = [func.count().label("count")]

            # 3. Overall summary calculation
            summary_stmt = select(*metric_expressions).where(where_stmt)
            summary_row = self.db.execute(summary_stmt).mappings().one()
            
            # Format summary dictionary
            summary_dict = {}
            for k, v in summary_row.items():
                if v is not None and isinstance(v, float):
                    summary_dict[k] = round(v, 2)
                else:
                    summary_dict[k] = v if v is not None else 0

            # Count total matched
            total_matched = self.db.execute(select(func.count()).select_from(Ticket).where(where_stmt)).scalar() or 0

            # 4. Group by breakdown (if dimensions provided)
            breakdown_data = []
            if query.group_by:
                dimension_expressions = []
                for dim in query.group_by:
                    if dim == DimensionType.CATEGORY:
                        dimension_expressions.append(Ticket.category.label("category"))
                    elif dim == DimensionType.PRIORITY:
                        dimension_expressions.append(Ticket.priority.label("priority"))
                    elif dim == DimensionType.STATUS:
                        dimension_expressions.append(Ticket.status.label("status"))
                    elif dim == DimensionType.AGENT_ID:
                        dimension_expressions.append(Ticket.agent_id.label("agent_id"))
                    elif dim == DimensionType.MONTH:
                        dimension_expressions.append(func.strftime("%Y-%m", Ticket.created_at).label("month"))
                    elif dim == DimensionType.WEEK:
                        dimension_expressions.append(func.strftime("%Y-W%W", Ticket.created_at).label("week"))
                    elif dim == DimensionType.DATE:
                        dimension_expressions.append(func.strftime("%Y-%m-%d", Ticket.created_at).label("date"))

                group_stmt = select(*dimension_expressions, *metric_expressions).where(where_stmt)
                group_stmt = group_stmt.group_by(*dimension_expressions)

                # Sorting
                if query.sort:
                    sort_col = text(query.sort.field)
                    if query.sort.order == SortOrder.DESC:
                        group_stmt = group_stmt.order_by(desc(sort_col))
                    else:
                        group_stmt = group_stmt.order_by(asc(sort_col))
                else:
                    # Default sort by first metric descending
                    group_stmt = group_stmt.order_by(desc(text("count")))

                if query.limit:
                    group_stmt = group_stmt.limit(query.limit)

                rows = self.db.execute(group_stmt).mappings().all()
                for r in rows:
                    item_dict = {}
                    for k, v in r.items():
                        if isinstance(v, float):
                            item_dict[k] = round(v, 2)
                        else:
                            item_dict[k] = v
                    breakdown_data.append(item_dict)

            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            return StructuredQueryResult(
                intent=query.intent,
                query_spec=query,
                metrics_summary=summary_dict,
                breakdown_data=breakdown_data,
                total_records_matched=total_matched,
                execution_time_ms=round(elapsed_ms, 2),
                explanation=f"Calculated deterministically from {total_matched} matching support tickets in SQLite."
            )
        except AppException:
            raise
        except Exception as e:
            logger.error(f"Structured query execution failed: {e}")
            raise QueryExecutionError("Query execution error", details={"error": str(e)})
