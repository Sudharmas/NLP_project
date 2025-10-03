from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class ConnectRequest(BaseModel):
    connection_string: str = Field(..., description="SQLAlchemy connection string, e.g., sqlite:///./demo.db")


class ConnectResponse(BaseModel):
    success: bool
    schema: Dict[str, Any]


class UploadDocumentsResponse(BaseModel):
    job_id: str
    accepted: int


class IngestionStatusResponse(BaseModel):
    job_id: str
    status: str
    processed: int
    total: int
    errors: List[str] = []


class QueryRequest(BaseModel):
    query: str
    page: int = 1
    page_size: int = 50


class QueryResponse(BaseModel):
    query_type: str
    results: Any
    sources: List[Dict[str, Any]] = []
    performance: Dict[str, Any]
    cache: Dict[str, Any]


class SchemaResponse(BaseModel):
    schema: Dict[str, Any]
