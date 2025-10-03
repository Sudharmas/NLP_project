import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from starlette.responses import FileResponse
from backend.api.routes import ingestion, query, schema
import structlog

logger = structlog.get_logger()

app = FastAPI(title="NLP Query Engine for Employee Data")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Performance middleware
import time
@app.middleware("http")
async def add_process_time_header(request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = (time.perf_counter() - start_time) * 1000
    response.headers["X-Process-Time"] = str(int(process_time))
    try:
        logger.info("request", path=str(request.url.path), method=request.method, ms=int(process_time))
    except Exception:
        pass
    return response

# Routers
app.include_router(ingestion.router, prefix="/api", tags=["ingestion"])
app.include_router(query.router, prefix="/api", tags=["query"])
app.include_router(schema.router, prefix="/api", tags=["schema"])

@app.get("/health")
async def health():
    return {"status": "ok"}


# Serve frontend static files (mounted last to avoid overshadowing API routes like /health)
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "public")
frontend_dir = os.path.abspath(frontend_dir)
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


# Uvicorn entrypoint: uvicorn backend.main:app --reload
