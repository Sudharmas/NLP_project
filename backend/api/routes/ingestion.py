from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
from typing import List
from ..services.app_state import get_app_state
from ..services.schema_discovery import SchemaDiscovery
from ..services.models import ConnectRequest, ConnectResponse, UploadDocumentsResponse, IngestionStatusResponse
import uuid

router = APIRouter()

@router.post("/connect-database", response_model=ConnectResponse)
async def connect_database(payload: ConnectRequest):
    state = get_app_state()
    try:
        discovery = SchemaDiscovery()
        schema = discovery.analyze_database(payload.connection_string)
        state.set_connection(payload.connection_string, schema)
        return ConnectResponse(success=True, schema=schema)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upload-documents", response_model=UploadDocumentsResponse)
async def upload_documents(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    # Lazy import to avoid heavy ML deps at startup/tests
    from ..services.document_processor import DocumentProcessor

    state = get_app_state()
    # Ensure storage directories exist even if DB is not connected
    try:
        state.ensure_storage_dirs()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to prepare storage: {e}")

    if files is None or len(files) == 0:
        raise HTTPException(status_code=400, detail="No files provided for upload.")

    job_id = str(uuid.uuid4())
    state.jobs[job_id] = {"status": "queued", "processed": 0, "total": len(files), "errors": []}

    # Save files to disk immediately to avoid closed-stream issues in background
    processor = DocumentProcessor(state)
    try:
        import aiofiles  # type: ignore
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"aiofiles not available: {e}")
    uploads_dir = state.storage_dirs["uploads"]
    saved_paths = []
    for f in files:
        safe_name = (f.filename or "upload.bin").split("/")[-1].split("\\")[-1]
        dest = uploads_dir / safe_name
        try:
            async with aiofiles.open(str(dest), "wb") as out:
                content = await f.read()
                await out.write(content)
            saved_paths.append(dest)
        except Exception as e:
            # Record error and continue with others
            state.jobs[job_id]["errors"].append(f"{safe_name}: {e}")
    # Update total to reflect actually saved files
    state.jobs[job_id]["total"] = len(saved_paths)

    async def run_job():
        try:
            await processor.process_files_from_paths(job_id, saved_paths)
        except Exception as e:
            state.jobs[job_id]["status"] = "failed"
            state.jobs[job_id]["errors"].append(str(e))

    background_tasks.add_task(run_job)
    return UploadDocumentsResponse(job_id=job_id, accepted=len(saved_paths))


@router.get("/ingestion-status/{job_id}", response_model=IngestionStatusResponse)
async def get_status(job_id: str):
    state = get_app_state()
    info = state.jobs.get(job_id)
    if not info:
        raise HTTPException(status_code=404, detail="Job not found")
    return IngestionStatusResponse(job_id=job_id, **info)
