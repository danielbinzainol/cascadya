from __future__ import annotations

import os
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from src.backoffice.persistence.database import get_query_engine

_BLOCKED_SQL_KEYWORDS = re.compile(
    r"\b("
    r"insert|update|delete|drop|alter|truncate|create|grant|revoke|"
    r"comment|vacuum|analyze|refresh|call|do|copy|merge"
    r")\b",
    flags=re.IGNORECASE,
)
_MAX_QUERY_LIMIT = int(os.getenv("BACKOFFICE_QUERY_MAX_ROWS", "1000"))
_DEFAULT_QUERY_LIMIT = int(os.getenv("BACKOFFICE_QUERY_DEFAULT_ROWS", "200"))
_STATEMENT_TIMEOUT_MS = int(os.getenv("BACKOFFICE_QUERY_TIMEOUT_MS", "15000"))


class QueryValidationError(ValueError):
    """Raised when SQL text violates query API constraints."""


def _normalize_and_validate_sql(sql: str) -> str:
    normalized = sql.strip()
    if not normalized:
        raise QueryValidationError("SQL query cannot be empty.")

    if ";" in normalized.rstrip(";"):
        raise QueryValidationError("Only one SQL statement is allowed.")
    normalized = normalized.rstrip(";").strip()

    lowered = normalized.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise QueryValidationError("Only SELECT/CTE read queries are allowed.")

    if _BLOCKED_SQL_KEYWORDS.search(lowered):
        raise QueryValidationError(
            "Write/DDL keywords are not allowed in query endpoint."
        )

    return normalized


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def run_read_query(sql: str, limit: int | None = None) -> dict[str, Any]:
    query = _normalize_and_validate_sql(sql)
    wanted = (
        _DEFAULT_QUERY_LIMIT if limit is None else max(1, min(limit, _MAX_QUERY_LIMIT))
    )

    engine = get_query_engine()
    timeout_ms = max(1, int(_STATEMENT_TIMEOUT_MS))
    with engine.connect() as conn:
        with conn.begin():
            conn.execute(text("SET TRANSACTION READ ONLY"))
            conn.execute(text(f"SET LOCAL statement_timeout = {timeout_ms}"))
            result = conn.execute(text(query))
            if not result.returns_rows:
                raise QueryValidationError("Query must return rows.")

            rows = result.mappings().fetchmany(wanted + 1)

    has_more = len(rows) > wanted
    rows = rows[:wanted]
    columns = list(rows[0].keys()) if rows else list(result.keys())
    data = [{key: _json_safe(value) for key, value in row.items()} for row in rows]
    return {
        "columns": columns,
        "rows": data,
        "row_count": len(data),
        "truncated": has_more,
        "limit": wanted,
    }
