# NLP Query Engine for Employee Data (LangChain)

A production‑minded demo that builds a natural language query system for employee databases and unstructured employee documents. It dynamically discovers schema (no hard‑coded column/table names), processes documents with embeddings, and supports SQL, document, and hybrid queries with caching and performance instrumentation.

Works with SQLite for demo, and supports PostgreSQL/MySQL via SQLAlchemy.

For a step-by-step setup, running, testing, and debugging guide, see EXECUTION_GUIDE.md.

## Features

- Dynamic schema discovery via SQLAlchemy Inspector (tables, columns, FKs, samples, and heuristic hints)
- Natural language to schema mapping using synonym/fuzzy matching (no hard-coded schema)
- Query Engine
  - Classification: SQL vs Document vs Hybrid
  - Safe SQL templates with parameterization for filters
  - Pagination (limit/offset) and lightweight optimization
  - Result caching (TTL LRU) with hit/miss metrics
- Document Pipeline (LangChain)
  - Upload multiple file types: PDF, DOCX, TXT, CSV
  - Dynamic chunking based on structure/type
  - Embeddings with sentence-transformers (HuggingFace) and Chroma persistent vector store
  - Background ingestion with job status
- Web UI (vanilla HTML/JS)
  - Connect database & visualize schema JSON
  - Upload docs with progress polling
  - Query input, results rendering (table/cards), metrics display
  - Query history dropdown
- Monitoring
  - Middleware adds X-Process-Time header (ms) and logs per request (structlog)
- Production-minded
  - Connection pooling (SQLAlchemy QueuePool)
  - Async endpoints, non-blocking IO for uploads
  - Error handling with clear messages

## Project Structure

```
project/
├── backend/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── ingestion.py
│   │   │   ├── query.py
│   │   │   └── schema.py
│   │   └── services/
│   │       ├── app_state.py
│   │       ├── document_processor.py
│   │       ├── models.py
│   │       ├── query_cache.py
│   │       ├── query_engine.py
│   │       └── schema_discovery.py
│   ├── __init__.py
│   └── main.py
├── frontend/
│   └── public/
│       ├── index.html
│       ├── app.js
│       └── styles.css
├── tests/
│   ├── conftest.py
│   ├── test_api_integration.py
│   ├── test_query_engine.py
│   └── test_schema_discovery.py
├── config.yml
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Configuration

Edit config.yml or environment variables. Defaults are sensible for demo.

```yaml
database:
  connection_string: ${DATABASE_URL}
  pool_size: 10
embeddings:
  model: sentence-transformers/all-MiniLM-L6-v2
  batch_size: 32
cache:
  ttl_seconds: 300
  max_size: 1000
storage:
  base_dir: ./data
  chroma_dir: ./data/chroma
logging:
  level: INFO
  json: true
server:
  host: 0.0.0.0
  port: 8000
  workers: 1
```

Set DATABASE_URL to override the DB connection string, or pass at runtime via the UI.

## Backend API

- POST /api/connect-database
  - Body: { "connection_string": "sqlite:///./demo.db" }
  - Returns discovered schema and initializes engine/cache/vectorstore directories
- POST /api/upload-documents
  - Form-Data: files[] (multiple)
  - Returns job_id
- GET /api/ingestion-status/{job_id}
  - Returns progress of document processing
- POST /api/query
  - Body: { "query": "Average salary by department", "page": 1, "page_size": 50 }
  - Returns results, sources, performance metrics, cache stats
- GET /api/query/history
  - Returns recent queries
- GET /api/schema
  - Returns discovered schema (tables, columns, FKs, hints)

## Running Locally

Option A: Python/uvicorn

1. python -m venv .venv && source .venv/bin/activate (Windows: .venv\\Scripts\\activate)
2. pip install -r requirements.txt
3. uvicorn backend.main:app --reload
4. Open http://localhost:8000

Option B: Docker Compose

1. docker-compose up --build
2. Open http://localhost:8000

## Demo Workflow

1. Connect Database
   - Example (SQLite file): sqlite:///./tests/test_demo.db
   - For Postgres: postgresql://user:pass@localhost:5432/company_db
2. Review Schema
   - JSON view shows tables and heuristic hints
3. Upload Documents (optional)
   - Drag/drop multiple PDFs/DOCX/TXT/CSV (max ~10MB each recommended)
   - Background job shows progress via polling
4. Query
   - Try: "How many employees do we have?"
   - Try: "Average salary by department"
   - Try: "Show me all Python developers in Engineering" (hybrid)

## Tests

- Run: pytest -q
- Integration test uses SQLite DB at tests/test_demo.db
- Document upload test is skipped to avoid heavy embedding downloads in CI; you can run ingestion manually in the app.

## Notes on Adaptability

- Schema Discovery uses SQLAlchemy inspector and heuristics to find employee- and department-like tables (based on synonyms) and likely column names (name, salary, department, date, manager). No hard-coded schema.
- Query Engine uses discovered hints and safe SQL generation for common patterns; complex multi-table joins beyond detected FKs are reduced to simpler queries with guidance.

## Performance & Security

- Caching: TTL LRU cache stores recent query results; cache hit rate shown in UI.
- Connection Pooling: SQLAlchemy QueuePool configured via config.yml.
- Async I/O: File uploads and reading via aiofiles; background ingestion with FastAPI BackgroundTasks.
- Pagination: LIMIT/OFFSET applied to SQL queries.
- SQL Injection: Parameters are bound safely for filters; table/column names are sourced from discovered schema (not user input). For production, consider stricter validation and query builders.
- Monitoring: Request time header and logs (structlog). You can add exporters or APM easily.

## Limitations

- NL2SQL is heuristic, not LLM-driven, to avoid paid API usage; it covers common patterns and name/department filters. You can plug an open-source LLM later.
- Vector search uses Chroma persistence; first run will download the embedding model (a few hundred MB). For tests/CI, ingestion is skipped.
- Schema visualization is a JSON tree; graph visualization can be added in UI later.

## FAQ

- Can I use other DBs? Yes, any SQLAlchemy-supported DB. Ensure network reachability and credentials.
- Large files? For this demo, try to keep files under ~10MB. Add file size checks in the upload route if needed.
- Authentication? Not included by design for the assignment. Add a reverse-proxy or simple auth if deploying.
# NLP_project
