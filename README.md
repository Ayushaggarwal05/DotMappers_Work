# TracePath AI - Customer Support Intelligence Platform

Production-quality AI Customer Support Ticket Analytics system and interactive intelligence dashboard built with **FastAPI**, **SQLite**, **SQLAlchemy**, **Pydantic**, and **Streamlit**.

---

## 🏛️ Architecture & LLM Safety Guarantees

The core design principle of TracePath AI is **strict separation between natural language understanding and database execution**:

```
Streamlit UI / REST Client
          ↓
FastAPI Layer (POST /api/query, GET /api/stats, GET /api/anomalies, GET /api/tickets)
          ↓
┌────────────────────────────────────────────────────────┐
│  LLM Intent Engine (xAI Grok / Zero-Cost Fallback)     │
│  → STRICT Pydantic StructuredIntent AST                │
└────────────────────────────────────────────────────────┘
          ↓
┌────────────────────────────────────────────────────────┐
│             Deterministic Routing & Execution          │
│                                                        │
│  • Anomaly Query?   ──►  Deterministic Anomaly Engine  │
│                           - Statistical IQR Detection  │
│                           - SLA Breach & Aging Rules   │
│                                                        │
│  • Analytics Query? ──►  Safe Parameterized SQLite     │
│                           - Safe SQL Engine            │
│                           - Aggregations & Breakdowns  │
└────────────────────────────────────────────────────────┘
          ↓
100% Grounded Mathematical Result & Factual Natural Language Answer
          ↓
Interactive Streamlit UI Dashboard
```

### Safety Principles:
1. **Zero Direct SQL Generation**: The LLM **never** generates executable SQL strings or arbitrary code.
2. **Zero SQL Injection**: Queries are constructed strictly from typed enums, whitelisted column names, and parameterized literals.
3. **Zero Credential Exposure**: Streamlit communicates strictly via HTTP with FastAPI without access to backend API keys or secrets.
4. **Zero Cost Evaluation**: Works completely out-of-the-box without requiring paid API keys. When `XAI_API_KEY` is provided in `.env`, it connects to xAI Grok.
5. **100% Grounded Answers**: Statistical calculations and counts are computed by SQLite, preventing LLM hallucinations.

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
│   │       ├── anomalies.py     # GET /api/anomalies Outlier & SLA violation endpoint
│   │       ├── stats.py         # GET /api/stats KPI metrics & chart distributions
│   │       └── tickets.py       # Ticket search, filtering, & pagination
│   ├── core/
│   │   ├── database.py          # SQLite engine, session management, WAL mode
│   │   ├── exceptions.py        # Unified exception hierarchy & global handlers
│   │   └── logging.py           # Structured logging configuration
│   ├── anomaly/
│   │   ├── detector.py          # Anomaly detection coordinator
│   │   ├── rules.py             # IQR statistical rules & aged SLA threshold rules
│   │   └── schemas.py           # AnomalyItem & AnomalyReport Pydantic schemas
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
│       ├── test_natural_language_queries.py # Assessment evaluation queries
│       ├── test_anomaly_detection.py        # Statistical IQR & SLA tests
│       ├── test_api_endpoints.py            # Full REST API endpoint tests
│       ├── test_repository.py   # Repository & metric aggregation tests
│       ├── test_schemas.py      # Pydantic schema validation tests
│       └── test_structured_queries.py # Structured query execution tests
│
├── frontend/
│   ├── app.py                   # Production-grade Streamlit Analytics Dashboard
│   └── api_client.py            # Centralized API client module
│
├── data/
│   └── support_tickets.csv      # 500-row support dataset
│
├── .streamlit/
│   └── config.toml              # Streamlit dark slate theme styling
├── .env                         # Local environment settings
├── .env.example                 # Example configuration template
├── .gitignore                   # Git ignore rules
├── requirements.txt             # Python dependencies
├── README.md                    # Project documentation
├── main.py                      # Root FastAPI entrypoint
└── run.py                       # Single-command concurrent launcher
```

---

## 🚀 Quick Start (One Command)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Launch TracePath AI (Backend + UI)
Launch both the FastAPI backend and Streamlit frontend concurrently:

```bash
python run.py
```

*Or run services in separate terminals:*

**Terminal 1 (Backend API):**
```bash
uvicorn backend.main:app --reload
```

**Terminal 2 (Streamlit UI):**
```bash
streamlit run frontend/app.py
```

- **Interactive Dashboard UI**: `http://localhost:8501`
- **Backend API & Swagger Docs**: `http://localhost:8000/docs`
- **Health Diagnostic**: `http://localhost:8000/health`

---

## 🖥️ Streamlit UI Features

| View | Features |
|---|---|
| **📊 Overview Dashboard** | Real-time KPI cards (Total, Open, Resolved, Escalated, Critical, Anomalies), avg response/resolution times, rating distribution, and interactive Altair charts by Category, Priority, Status, and Agent. |
| **💬 Ask AI** | Natural language query box with 1-click assessment question buttons, prominent grounded answer card, metadata pills (Execution Time ms, Matched Records, Anomaly Flag), and expandable Pydantic Intent AST inspector. |
| **⚠️ Anomaly Center** | Statistical IQR baseline summary ($Q1$, Median, $Q3$, $\text{IQR}$, Upper Outlier Threshold: $48.15\text{h}$), severity and type filter controls, and detailed anomaly cards with exact metrics and reasons. |
| **🔍 Ticket Explorer** | Multi-attribute filtering (Category, Priority, Status, Agent, Search text), page-size selection, pagination controls, and tabular ticket view. |
| **⚙️ System Status** | Live diagnostic inspection of API health, database connection, dataset path, loaded ticket count (`500`), and server uptime. |

---

## 📡 Complete REST API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | System health, database connectivity, and loaded ticket count (`500`) |
| `POST` | `/api/query` | Natural language query translation and execution |
| `GET` | `/api/stats` | Executive KPI metrics (counts, rates, averages, anomaly count) |
| `GET` | `/api/stats/breakdown` | Categorical and dimensional distribution data for visual charts |
| `GET` | `/api/anomalies` | Detected statistical outliers and aged SLA violations (filterable by type & severity) |
| `GET` | `/api/tickets` | Paginated ticket search with category, priority, status, and agent filters |
| `GET` | `/api/tickets/{ticket_id}` | Retrieve details for a single support ticket |

---

## 🧪 Verified Assessment Queries (Live Execution Results)

```text
Q1: "How many tickets are currently open?"
→ Intent: COUNT
→ Answer: "There are 111 Open tickets in the system." (Matched: 111 | Timing: 4.7 ms)

Q2: "Which agent resolved the most tickets this month?"
→ Intent: TOP_N
→ Answer: "Agent AGT-01 is the top performer with 16 tickets." (Matched: 121 | Timing: 9.5 ms)

Q3: "Show me all Critical tickets not resolved within 12 hours."
→ Intent: FILTER
→ Answer: "Found 3 tickets matching your criteria (priority eq 'Critical', resolution_time_hrs gt '12.0'). Returning 3 records." (Matched: 3 | Timing: 6.3 ms)

Q4: "What is the average customer rating for Technical category tickets?"
→ Intent: AGGREGATION
→ Answer: "The average customer rating for Technical category tickets is 3.74 out of 5 (across 152 tickets)." (Matched: 152 | Timing: 4.8 ms)

Q5: "Are there any anomalies in resolution times this week?"
→ Intent: ANOMALY_DETECTION
→ Answer: "Detected 8 anomalies. Found 2 tickets exceeding the IQR resolution time threshold (87.55 hrs) and 6 high-priority tickets unresolved for >24 hours." (Matched: 8 | Timing: 8.5 ms)
```

---

## 🧪 Running Automated Tests

Run the complete 42-test suite with `pytest`:

```bash
pytest -v
```
