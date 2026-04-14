import re
from pathlib import Path

from fastapi import HTTPException


MARKET_ORDERS_DIR = (Path("data/market_orders")).resolve()
PROJECT_RE = re.compile(r"^[A-Za-z0-9_-]+$")
FILE_ID_RE = re.compile(r"^\d{8}_\d{8}_\d{4}$")


def resolve_market_orders_csv_path(project: str, file_id: str) -> Path:
    if not PROJECT_RE.fullmatch(project):
        raise HTTPException(status_code=400, detail="Invalid project format.")
    if not FILE_ID_RE.fullmatch(file_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid file_id format. Expected YYYYMMDD_YYYYMMDD_HHMM.",
        )

    csv_filename = f"{project}_{file_id}.csv"
    csv_path = (MARKET_ORDERS_DIR / csv_filename).resolve()
    if csv_path.parent != MARKET_ORDERS_DIR:
        raise HTTPException(
            status_code=400, detail="Resolved path is outside allowed directory."
        )
    if not csv_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"CSV file not found for project={project}, file_id={file_id}.",
        )
    return csv_path
