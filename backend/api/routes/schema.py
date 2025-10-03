from fastapi import APIRouter, HTTPException
from ..services.app_state import get_app_state
from ..services.models import SchemaResponse

router = APIRouter()


@router.get("/schema", response_model=SchemaResponse)
async def get_schema():
    state = get_app_state()
    if not state.schema:
        raise HTTPException(status_code=404, detail="Schema not available. Connect to a database first.")
    return SchemaResponse(schema=state.schema)
