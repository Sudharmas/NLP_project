from fastapi import APIRouter, HTTPException
from ..services.app_state import get_app_state
from ..services.query_engine import QueryEngine
from ..services.models import QueryRequest, QueryResponse

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def process_query(payload: QueryRequest):
    state = get_app_state()
    if not state.is_initialized():
        raise HTTPException(status_code=400, detail="Database not connected. Connect first to initialize services.")
    engine = QueryEngine(state)
    resp = engine.process_query(payload.query, page=payload.page, page_size=payload.page_size)
    return QueryResponse(**resp)


@router.get("/query/history")
async def query_history():
    state = get_app_state()
    return list(reversed(state.query_history))
