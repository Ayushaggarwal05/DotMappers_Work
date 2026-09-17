# TracePath AI - Customer Support Analytics & NL Query Engine

Production-quality AI Customer Support Ticket Analytics system built with **FastAPI**, **SQLite**, **SQLAlchemy**, **Pydantic**, and **xAI/Grok (with zero-cost fallback)**.

---

## 🏛️ Architectural Design & Safety Guarantee

The core design principle of TracePath AI is **strict separation between natural language understanding and database execution**:

```
User Query (Natural Language)
          ↓
FastAPI Layer (POST /api/query)
          ↓
LLM Intent Engine (xAI Grok / Zero-Cost Fallback Provider)
          ↓
STRICT Structured Query Schema (Pydantic AST / FilterClauses / Metrics / DateRanges)
          ↓
Validation Layer (Allowlists, Enum validation, Date resolution)
          ↓
Deterministic Parameterized SQLite Execution (SQLAlchemy / Safe Parameterized SQL)
          ↓
Grounded Mathematical Result & Factual Answer Generation
          ↓
FastAPI Response & Streamlit Dashboard
```

### Safety Principles:
1. **Zero Direct SQL Generation**: The LLM **never** generates executable SQL strings or arbitrary code.
2. **Zero SQL Injection**: Queries are constructed strictly from typed enums, whitelisted column names, and parameterized literals.
3. **Zero Cost Evaluation**: Works completely out-of-the-box without requiring paid API keys. When `XAI_API_KEY` is provided in `.env`, it seamlessly connects to xAI Grok.
4. **100% Grounded Answers**: Numerical results are computed by the database query engine, preventing LLM hallucinations.

---

## 📁 Project Structure

```
tracepath-ai/
│
├── backend/
│   ├── main.py                  # FastAPI application factory & lifespan hooks
│   ├── config.py                # Environment-driven settings (pydantic-settings)
│   ├── api/
│   │   ├── dependencies.py      # Dependency injection providers (db, services, llm)
│   │   └── routes/
│   │       ├── health.py        # /health diagnostic endpoint
│   │       ├── query.py         # POST /api/query Natural language query endpoint
│   │       └── tickets.py       # Ticket search, aggregation, & query execution
│   ├── core/
│   │   ├── database.py          # SQLite engine, session management, WAL mode
│   │   ├── exceptions.py        # Unified exception hierarchy & global handlers
│   │   └── logging.py           # Structured logging configuration
│   ├── llm/
│   │   ├── base.py              # BaseLLMProvider abstract interface
│   │   ├── xai_provider.py      # xAI Grok client + Zero-Cost Semantic Fallback
│   │   ├── prompts.py           # System prompt, strict JSON schema & few-shot examples
│   │   └── parser.py            # Clean JSON extractor & Pydantic validator with retry
│   ├── query_engine/
│   │   ├── intent_schema.py     # Strict Pydantic Intent AST schema
│   │   ├── validator.py         # Allowlist validator & date range resolver
│   │   └── executor.py          # Safe parameterized SQL engine & answer generator
│   ├── models/
│   │   └── ticket.py            # SQLAlchemy Ticket ORM model with composite indexes
│   ├── schemas/
│   │   ├── common.py            # Enums (Category, Priority, Status) & API wrappers
│   │   ├── ticket.py            # Ticket Pydantic schemas & filter models
│   │   └── query.py             # Internal query AST models
│   ├── repositories/
│   │   └── ticket_repository.py # Parameterized data access & analytics engine
│   ├── services/
│   │   ├── ingestion_service.py # CSV parsing, normalization, validation, bulk upsert
│   │   └── ticket_service.py    # Business logic orchestration
│   └── tests/
│       ├── conftest.py          # In-memory SQLite fixtures & TestClient
│       ├── test_health.py       # Health check test suite
│       ├── test_ingestion.py    # CSV validation & parsing tests
│       ├── test_llm_engine.py   # Intent parser & schema validation tests
│       ├── test_natural_language_queries.py # End-to-end evaluation queries
│       ├── test_repository.py   # Repository & metric aggregation tests
│       ├── test_schemas.py      # Pydantic schema validation tests
│       └── test_structured_queries.py # Structured query execution tests
│
├── frontend/
│   └── app.py                   # Interactive Streamlit analytics dashboard
│
├── data/
│   └── support_tickets.csv      # 500-row support dataset
│
├── .env                         # Local environment settings
├── .env.example                 # Example configuration template
├── .gitignore                   # Git ignore rules
├── requirements.txt             # Python dependencies
├── README.md                    # Project documentation
└── main.py                      # Root one-command entrypoint
```

---

## 🚀 Quick Start (Single Command)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Application
Start the backend with a single command:

```bash
python main.py
```
*Alternatively:*
```bash
uvicorn backend.main:app --reload
```

The server will automatically:
1. Initialize the SQLite database schema (`support_analytics.db`).
2. Validate and auto-ingest the 500 tickets from `data/support_tickets.csv`.
3. Start the API server at `http://localhost:8000`.

Interactive Swagger documentation is available at **`http://localhost:8000/docs`**.

---

## 💬 Natural Language Query API (`POST /api/query`)

### Request
```bash
curl -X POST http://localhost:8000/api/query \
     -H "Content-Type: application/json" \
     -d '{"question": "How many critical tickets are unresolved?"}'
```

### Response
```json
{
  "question": "How many critical tickets are unresolved?",
  "interpretation": {
    "intent": "count",
    "metrics": ["count"],
    "group_by": [],
    "filters": [
      {"field": "priority", "operator": "eq", "value": "Critical"},
      {"field": "status", "operator": "in", "value": ["Open", "Escalated"]}
    ],
    "date_range": null,
    "sort": null,
    "limit": 100,
    "anomaly_request": false,
    "unresolved_only": true,
    "raw_question": "How many critical tickets are unresolved?",
    "confidence": 0.98,
    "notes": "Semantic rule-based intent parsing"
  },
  "answer": "There are 15 Open, Escalated tickets in the system.",
  "data": [
    {"count": 15}
  ],
  "metadata": {
    "execution_time_ms": 2.45,
    "total_records_matched": 15,
    "is_anomaly_request": false,
    "status": "success"
  }
}
```

---

## 🧪 Verified Assessment Queries

All 5 core evaluation query types are supported and tested:

1. **COUNT**: *"How many tickets are currently open?"*  
   → Returns exact count (`111` open tickets)
2. **SORT / TOP N**: *"Which agent resolved the most tickets this month?"*  
   → Groups by agent, filters resolved tickets, ranks descending
3. **FILTER**: *"Show me all Critical tickets not resolved within 12 hours."*  
   → Filters `priority=Critical` and `resolution_time_hrs > 12.0`
4. **AGGREGATION**: *"What is the average customer rating for Technical category tickets?"*  
   → Calculates exact mean customer rating (`3.74 / 5`)
5. **ANOMALY DETECTION**: *"Are there any anomalies in resolution times this week?"*  
   → Routes to the dedicated anomaly detection service integration point

---

## 🧪 Running Automated Tests

Run the complete 31-test suite with `pytest`:

```bash
pytest -v
```

---

## 💻 Interactive Streamlit UI

Launch the UI dashboard to ask questions interactively:

```bash
streamlit run frontend/app.py
```
Open `http://localhost:8501` in your browser.
