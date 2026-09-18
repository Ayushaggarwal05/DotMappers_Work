import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import (
    select, func, and_, or_, desc, asc, case, cast, Float, Integer, text
)

from backend.models.ticket import Ticket
from backend.query_engine.intent_schema import (
    StructuredIntent, QueryIntentType, MetricType, DimensionType,
    FilterOperator, FilterClause, SortOrder
)
from backend.query_engine.validator import IntentValidator
from backend.core.exceptions import QueryExecutionError
from backend.core.logging import logger


class QueryExecutor:
    """
    Deterministic Query Execution Engine.
    
    Guarantees:
    - Zero arbitrary SQL from LLM.
    - Safe execution of strictly validated Pydantic AST representations.
    - Factual answers derived 100% from SQLite data layer.
    """

    def __init__(self, db: Session):
        self.db = db
        self.validator = IntentValidator(db)

    def _build_filter_expressions(self, filters: List[FilterClause], date_range) -> List[Any]:
        """Convert FilterClauses to parameterized SQLAlchemy BinaryExpressions."""
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

        clauses = []
        for f in filters:
            col = col_map.get(f.field)
            if col is None:
                continue

            op = f.operator
            val = f.value

            if op == FilterOperator.EQ:
                clauses.append(col == val)
            elif op == FilterOperator.NEQ:
                clauses.append(col != val)
            elif op == FilterOperator.IN:
                val_list = val if isinstance(val, list) else [val]
                clauses.append(col.in_(val_list))
            elif op == FilterOperator.NOT_IN:
                val_list = val if isinstance(val, list) else [val]
                clauses.append(col.not_in(val_list))
            elif op == FilterOperator.GT:
                clauses.append(col > val)
            elif op == FilterOperator.GTE:
                clauses.append(col >= val)
            elif op == FilterOperator.LT:
                clauses.append(col < val)
            elif op == FilterOperator.LTE:
                clauses.append(col <= val)
            elif op == FilterOperator.LIKE:
                clauses.append(col.ilike(f"%{val}%"))
            elif op == FilterOperator.IS_NULL:
                clauses.append(col.is_(None))
            elif op == FilterOperator.NOT_NULL:
                clauses.append(col.isnot(None))

        if date_range:
            if date_range.start_date:
                clauses.append(Ticket.created_at >= date_range.start_date)
            if date_range.end_date:
                clauses.append(Ticket.created_at <= date_range.end_date)

        return clauses

    def _build_metric_expressions(self, metrics: List[MetricType]) -> List[Any]:
        """Convert MetricType enums into aggregate SQL expressions."""
        exprs = []
        for m in metrics:
            if m == MetricType.COUNT:
                exprs.append(func.count().label("count"))
            elif m == MetricType.AVG_RESPONSE_TIME:
                exprs.append(func.avg(Ticket.response_time_hrs).label("avg_response_time"))
            elif m == MetricType.AVG_RESOLUTION_TIME:
                exprs.append(func.avg(Ticket.resolution_time_hrs).label("avg_resolution_time"))
            elif m == MetricType.AVG_RATING:
                exprs.append(func.avg(Ticket.customer_rating).label("avg_rating"))
            elif m == MetricType.RESOLUTION_RATE:
                resolved_cases = func.sum(case((Ticket.status == "Resolved", 1.0), else_=0.0))
                total_cases = func.cast(func.count(), Float)
                exprs.append((resolved_cases / func.nullif(total_cases, 0) * 100.0).label("resolution_rate"))
            elif m == MetricType.ESCALATION_RATE:
                escalated_cases = func.sum(case((Ticket.status == "Escalated", 1.0), else_=0.0))
                total_cases = func.cast(func.count(), Float)
                exprs.append((escalated_cases / func.nullif(total_cases, 0) * 100.0).label("escalation_rate"))
            elif m == MetricType.SLA_BREACH_COUNT:
                exprs.append(
                    func.sum(
                        case((or_(Ticket.response_time_hrs > 4.0, Ticket.resolution_time_hrs > 48.0), 1), else_=0)
                    ).label("sla_breach_count")
                )
            elif m == MetricType.MIN_RESPONSE_TIME:
                exprs.append(func.min(Ticket.response_time_hrs).label("min_response_time"))
            elif m == MetricType.MAX_RESPONSE_TIME:
                exprs.append(func.max(Ticket.response_time_hrs).label("max_response_time"))
            elif m == MetricType.MIN_RESOLUTION_TIME:
                exprs.append(func.min(Ticket.resolution_time_hrs).label("min_resolution_time"))
            elif m == MetricType.MAX_RESOLUTION_TIME:
                exprs.append(func.max(Ticket.resolution_time_hrs).label("max_resolution_time"))

        if not exprs:
            exprs = [func.count().label("count")]
        return exprs

    def _build_dimension_expressions(self, dims: List[DimensionType]) -> List[Any]:
        """Convert DimensionType enums to SQL grouping expressions."""
        exprs = []
        for d in dims:
            if d == DimensionType.CATEGORY:
                exprs.append(Ticket.category.label("category"))
            elif d == DimensionType.PRIORITY:
                exprs.append(Ticket.priority.label("priority"))
            elif d == DimensionType.STATUS:
                exprs.append(Ticket.status.label("status"))
            elif d == DimensionType.AGENT_ID:
                exprs.append(Ticket.agent_id.label("agent_id"))
            elif d == DimensionType.MONTH:
                exprs.append(func.strftime("%Y-%m", Ticket.created_at).label("month"))
            elif d == DimensionType.WEEK:
                exprs.append(func.strftime("%Y-W%W", Ticket.created_at).label("week"))
            elif d == DimensionType.DATE:
                exprs.append(func.strftime("%Y-%m-%d", Ticket.created_at).label("date"))
        return exprs

    def execute(self, raw_intent: StructuredIntent) -> Dict[str, Any]:
        """
        Execute validated intent deterministically.
        Returns complete API query response.
        """
        start_time = time.perf_counter()
        intent = self.validator.validate_and_normalize(raw_intent)

        # 1. Check if Anomaly Detection request
        if intent.anomaly_request or intent.intent == QueryIntentType.ANOMALY_DETECTION:
            from backend.anomaly.detector import AnomalyDetector
            detector = AnomalyDetector(self.db)
            
            start_dt = intent.date_range.start_date if intent.date_range else None
            end_dt = intent.date_range.end_date if intent.date_range else None
            report = detector.detect_anomalies(start_date=start_dt, end_date=end_dt)
            
            elapsed = (time.perf_counter() - start_time) * 1000.0
            
            items_data = [item.model_dump() for item in report.items]
            long_res_count = report.anomalies_by_type.get("long_resolution_time", 0)
            aged_count = report.anomalies_by_type.get("unresolved_high_priority_aged", 0)
            upper_b = report.iqr_statistics.get("upper_bound", 0.0)

            if report.total_anomalies_detected > 0:
                answer = (
                    f"Detected {report.total_anomalies_detected} anomalies. "
                    f"Found {long_res_count} tickets exceeding the IQR resolution time threshold ({upper_b} hrs) "
                    f"and {aged_count} high-priority tickets unresolved for >24 hours."
                )
            else:
                answer = "No anomalies detected in resolution times or SLA breaches for the requested period."

            return {
                "question": intent.raw_question,
                "interpretation": intent.model_dump(),
                "answer": answer,
                "data": items_data,
                "metadata": {
                    "execution_time_ms": round(elapsed, 2),
                    "total_records_matched": report.total_anomalies_detected,
                    "is_anomaly_request": True,
                    "anomalies_by_type": report.anomalies_by_type,
                    "iqr_statistics": report.iqr_statistics,
                    "status": "success"
                }
            }

        # 2. Check for unsupported questions
        if intent.intent == QueryIntentType.UNSUPPORTED:
            elapsed = (time.perf_counter() - start_time) * 1000.0
            return {
                "question": intent.raw_question,
                "interpretation": intent.model_dump(),
                "answer": "This question cannot be mapped to a supported customer support analytics query.",
                "data": [],
                "metadata": {
                    "execution_time_ms": round(elapsed, 2),
                    "total_records_matched": 0,
                    "is_anomaly_request": False,
                    "status": "unsupported"
                }
            }

        # 3. Build SQL Where clauses
        filter_exprs = self._build_filter_expressions(intent.filters, intent.date_range)
        where_clause = and_(*filter_exprs) if filter_exprs else True

        # Total matched records count
        total_matched = self.db.execute(
            select(func.count()).select_from(Ticket).where(where_clause)
        ).scalar() or 0

        # Execute based on intent
        if intent.intent == QueryIntentType.FILTER:
            # Return detailed list of matching tickets
            query = select(Ticket).where(where_clause).order_by(desc(Ticket.created_at))
            if intent.limit:
                query = query.limit(intent.limit)
            
            rows = self.db.execute(query).scalars().all()
            data = [
                {
                    "ticket_id": t.ticket_id,
                    "created_at": t.created_at.strftime("%Y-%m-%d %H:%M"),
                    "category": t.category,
                    "priority": t.priority,
                    "status": t.status,
                    "response_time_hrs": t.response_time_hrs,
                    "resolution_time_hrs": t.resolution_time_hrs,
                    "agent_id": t.agent_id,
                    "customer_rating": t.customer_rating,
                    "issue_summary": t.issue_summary
                }
                for t in rows
            ]
            answer = self._generate_filter_answer(intent, total_matched, len(data))

        elif intent.intent in (QueryIntentType.GROUP_BY, QueryIntentType.TOP_N):
            # Grouped breakdown
            dims = self._build_dimension_expressions(intent.group_by)
            metrics = self._build_metric_expressions(intent.metrics)

            stmt = select(*dims, *metrics).where(where_clause).group_by(*dims)

            # Apply sorting
            if intent.sort:
                sort_col = text(intent.sort.field)
                if intent.sort.order == SortOrder.DESC:
                    stmt = stmt.order_by(desc(sort_col))
                else:
                    stmt = stmt.order_by(asc(sort_col))
            else:
                stmt = stmt.order_by(desc(text("count")))

            if intent.limit:
                stmt = stmt.limit(intent.limit)

            results = self.db.execute(stmt).mappings().all()
            data = []
            for r in results:
                row_dict = {}
                for k, v in r.items():
                    row_dict[k] = round(v, 2) if isinstance(v, float) else v
                data.append(row_dict)

            answer = self._generate_grouped_answer(intent, data)

        else:
            # COUNT or AGGREGATION
            metrics = self._build_metric_expressions(intent.metrics)
            stmt = select(*metrics).where(where_clause)
            row = self.db.execute(stmt).mappings().one()

            summary = {}
            for k, v in row.items():
                summary[k] = round(v, 2) if isinstance(v, float) else v
            
            data = [summary]
            answer = self._generate_aggregation_answer(intent, summary, total_matched)

        elapsed = (time.perf_counter() - start_time) * 1000.0

        return {
            "question": intent.raw_question,
            "interpretation": intent.model_dump(),
            "answer": answer,
            "data": data,
            "metadata": {
                "execution_time_ms": round(elapsed, 2),
                "total_records_matched": total_matched,
                "is_anomaly_request": False,
                "status": "success"
            }
        }

    def _generate_filter_answer(self, intent: StructuredIntent, total: int, returned: int) -> str:
        """Formulate a grounded natural-language answer for filtered ticket lists."""
        filter_descs = []
        for f in intent.filters:
            filter_descs.append(f"{f.field} {f.operator.value} '{f.value}'")
        
        filter_str = f" ({', '.join(filter_descs)})" if filter_descs else ""
        if total == 0:
            return f"Found 0 tickets matching the requested criteria{filter_str}."
        return f"Found {total} tickets matching your criteria{filter_str}. Returning {returned} records."

    def _generate_aggregation_answer(self, intent: StructuredIntent, summary: Dict[str, Any], total: int) -> str:
        """Formulate a grounded natural-language answer for single aggregations."""
        if total == 0:
            return "No matching tickets were found in the dataset for this query."

        answers = []
        if "count" in summary and len(summary) == 1:
            # Single count
            status_filter = next((f.value for f in intent.filters if f.field == "status"), None)
            cat_filter = next((f.value for f in intent.filters if f.field == "category"), None)
            prio_filter = next((f.value for f in intent.filters if f.field == "priority"), None)
            agent_filter = next((f.value for f in intent.filters if f.field == "agent_id"), None)

            status_str = ""
            if status_filter:
                if isinstance(status_filter, list):
                    status_str = "unresolved " if set(status_filter) == {"Open", "Escalated"} else f"{'/'.join(status_filter)} "
                else:
                    status_str = f"{status_filter} "
            elif intent.unresolved_only:
                status_str = "unresolved "

            prio_str = f"{prio_filter} " if prio_filter else ""
            cat_str = f"{cat_filter} " if cat_filter else ""
            agent_str = f" assigned to {agent_filter}" if agent_filter else ""

            qualifier = f"{status_str}{prio_str}{cat_str}".strip()
            if qualifier:
                return f"There are {summary['count']} {qualifier} tickets{agent_str} in the system."
            return f"There are {summary['count']} tickets matching the query."

        if "avg_rating" in summary:
            cat_filter = next((f.value for f in intent.filters if f.field == "category"), None)
            target = f" for {cat_filter} category tickets" if cat_filter else ""
            answers.append(f"The average customer rating{target} is {summary['avg_rating']} out of 5 (across {total} tickets).")

        if "avg_resolution_time" in summary:
            answers.append(f"The average resolution time is {summary['avg_resolution_time']} hours.")

        if "avg_response_time" in summary:
            answers.append(f"The average initial response time is {summary['avg_response_time']} hours.")

        if "resolution_rate" in summary:
            answers.append(f"The resolution rate is {summary['resolution_rate']}%.")

        return " ".join(answers) if answers else f"Calculated metrics across {total} tickets: {summary}"

    def _generate_grouped_answer(self, intent: StructuredIntent, data: List[Dict[str, Any]]) -> str:
        """Formulate a grounded natural-language answer for grouped and ranking queries."""
        if not data:
            return "No data found for the specified grouping dimensions."

        if intent.intent == QueryIntentType.TOP_N or (intent.sort and len(data) > 0):
            top_item = data[0]
            if "agent_id" in top_item:
                if "avg_rating" in top_item:
                    return f"Agent {top_item['agent_id']} has the highest average customer rating of {top_item['avg_rating']} out of 5."
                elif "avg_resolution_time" in top_item:
                    return f"Agent {top_item['agent_id']} has the fastest average resolution time of {top_item['avg_resolution_time']} hours."
                elif "avg_response_time" in top_item:
                    return f"Agent {top_item['agent_id']} has an average response time of {top_item['avg_response_time']} hours."
                elif "count" in top_item:
                    return f"Agent {top_item['agent_id']} is the top performer with {top_item['count']} tickets."
                else:
                    return f"Agent {top_item['agent_id']} ranks top with metric {top_item}."
            elif "category" in top_item:
                if "avg_rating" in top_item:
                    return f"Category '{top_item['category']}' has an average rating of {top_item['avg_rating']} out of 5."
                count_val = top_item.get("count", "N/A")
                return f"Category '{top_item['category']}' has the highest volume with {count_val} tickets."

        dim_names = ", ".join([d.value for d in intent.group_by])
        return f"Grouped analysis across {len(data)} distinct {dim_names} segments completed."
