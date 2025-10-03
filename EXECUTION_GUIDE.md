# Execution Guide: Run, Test, and Debug

This guide provides step-by-step instructions to set up, run, test, and debug the NLP Query Engine project.

If you run into issues, see the Troubleshooting section at the bottom. For deeper project details, see README.md.


## 1. Prerequisites

- Python 3.9–3.12
- Git
- Recommended: virtual environment (venv)
- Optional: Docker + Docker Compose (for containerized run)
- 8 GB RAM recommended


## 2. Clone and Setup

- Clone the repo and enter the folder
  - git clone <your-repo-url>
  - cd NLP_project

- Create and activate virtual environment
  - python -m venv .venv
  - source .venv/bin/activate  # Windows: .venv\Scripts\activate

- Install dependencies
  - pip install -r requirements.txt

- Optional: Set environment variables (override config.yml)
  - export DATABASE_URL="sqlite:///./tests/test_demo.db"  # or Postgres/MySQL URL


## 3. Run the App (Local)

Option A: Uvicorn (recommended for development)
- uvicorn backend.main:app --reload
- Open http://localhost:8000 in your browser

Option B: Docker Compose
- docker-compose up --build
- Open http://localhost:8000


## 4. Typical Demo Flow

1) Connect to a database
- Use the UI at http://localhost:8000
- Example (SQLite demo DB created by tests): sqlite:///./tests/test_demo.db
- For Postgres: postgresql://user:pass@localhost:5432/company_db

2) Review discovered schema
- The UI shows schema JSON (tables, columns, foreign keys, hints)

3) Upload documents (optional)
- Drag-and-drop PDFs/DOCX/TXT/CSV files
- Processing is asynchronous; check ingestion status in UI

4) Run queries
- Examples:
  - "How many employees do we have?" (SQL)
  - "Average salary by department" (SQL)
  - "Show me all Python developers in Engineering" (Hybrid)


## 5. API Quick Reference (cURL)

Connect DB
- curl -X POST http://localhost:8000/api/connect-database \
  -H "Content-Type: application/json" \
  -d '{"connection_string": "sqlite:///./tests/test_demo.db"}'

Query
- curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How many employees do we have?", "page": 1, "page_size": 50}'

Schema
- curl http://localhost:8000/api/schema

History
- curl http://localhost:8000/api/query/history

Ingestion Status
- curl http://localhost:8000/api/ingestion-status/<JOB_ID>


## 6. Running Tests

- Run all tests
  - pytest -q

- Run a subset
  - pytest -k query_engine -q

- View verbose output
  - pytest -vv

Notes:
- Tests create a demo SQLite DB at tests/test_demo.db.
- Document upload test is skipped to avoid downloading large ML models in CI. You can run ingestion manually via the UI to validate docs pipeline locally.


## 7. Debugging Guide

Enable detailed logs
- Set log level in config.yml:
  logging:
    level: DEBUG
    json: false
- Or override at runtime via environment variables by editing config.yml, then restart the app.

Inspect performance per request
- Every HTTP response contains header: X-Process-Time (ms).
- Logs include per-request structured entries (path, method, ms).

SQLAlchemy echo
- Temporarily enable SQL logging by editing backend/api/services/app_state.py -> create_engine(..., echo=True) for local debugging.

Interactive debugging (VS Code example)
- Use a Python debug configuration with module: uvicorn, args: backend.main:app --reload.

Manual function-level checks
- Schema Discovery:
  - from backend.api.services.schema_discovery import SchemaDiscovery
  - SchemaDiscovery().analyze_database("sqlite:///./tests/test_demo.db")
- Query Engine:
  - from backend.api.services.app_state import AppState
  - from backend.api.services.schema_discovery import SchemaDiscovery
  - from backend.api.services.query_engine import QueryEngine
  - s = AppState(); conn = "sqlite:///./tests/test_demo.db"; s.set_connection(conn, SchemaDiscovery().analyze_database(conn))
  - QueryEngine(s).process_query("Average salary by department")
- Document Processor (manual ingestion):
  - Use the UI or write a small script to call /api/upload-documents with FormData.

Common breakpoints
- backend/main.py: request middleware, router registration
- backend/api/routes/*.py: endpoints
- backend/api/services/query_engine.py: classify/process_query/_run_sql_query/_search_documents
- backend/api/services/schema_discovery.py: analyze_database/map_natural_language_to_schema
- backend/api/services/document_processor.py: process_uploads/dynamic_chunking


## 8. Troubleshooting

Port already in use
- Change port: uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload

Import errors in backend.main
- Ensure you run with the project root on PYTHONPATH.
- Use uvicorn backend.main:app from the repo root directory.

Database connection errors
- Verify connection string (supports SQLite, Postgres, MySQL via SQLAlchemy).
- For SQLite, ensure the file path exists and is writable.

Embeddings/model download too slow
- First run downloads the sentence-transformers model (hundreds of MB). If you only need SQL, skip document ingestion.

Chroma persistence permission issues
- The vector store writes under ./data/chroma; ensure the directory is writable.

Query returns empty or errors
- The NL2SQL mapping is heuristic; try simpler queries or ensure your schema has employee-like tables (employees/staff/personnel) and columns.


## 9. Final Setup Checklist

- [ ] Python venv created and dependencies installed
- [ ] App starts: uvicorn backend.main:app --reload
- [ ] Connect to demo DB: sqlite:///./tests/test_demo.db
- [ ] Schema displays in UI
- [ ] Run sample queries successfully
- [ ] (Optional) Upload small sample documents and verify retrieval
- [ ] Tests pass: pytest -q


## 10. Project Structure Reminder

See README.md for a detailed tree. Key folders:
- backend/ (FastAPI app, services)
- frontend/public/ (static UI)
- tests/ (unit/integration tests, demo DB)


## 11. Notes on Performance & Safety

- Query caching is enabled (TTL LRU). Cache hit rate is returned in /api/query responses.
- Safe SQL templates avoid direct string concatenation with user parameters for filters.
- Pagination (LIMIT/OFFSET) added automatically to prevent large result sets.
- Background ingestion with progress tracking for documents.


## 12. Support

If you encounter issues not covered here, check the README.md Limitations section and open an issue in your repository with logs and steps to reproduce.
