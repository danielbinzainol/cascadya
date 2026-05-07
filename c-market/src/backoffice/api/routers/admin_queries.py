from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from src.backoffice.services.query_service import QueryValidationError, run_read_query

router = APIRouter(prefix="/admin/query", tags=["admin-query"])


class QueryRequest(BaseModel):
    sql: str = Field(..., description="Single read-only SQL query (SELECT / WITH).")
    limit: int | None = Field(default=None, ge=1, le=1000)


class QueryResponse(BaseModel):
    columns: list[str]
    rows: list[dict[str, object]]
    row_count: int
    truncated: bool
    limit: int


@router.post("/run", response_model=QueryResponse)
async def run_query(payload: QueryRequest) -> QueryResponse:
    try:
        result = run_read_query(payload.sql, payload.limit)
    except QueryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=400, detail=f"SQL execution failed: {exc}"
        ) from exc
    return QueryResponse(**result)
