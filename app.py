import uvicorn
import re
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from src.ingest import data_workflow
from src.market_orders import complex_market_orders_data_workflow
from plots import plot_market_orders

"""
Use: run this file in debug mode, with F5.
Go to the local url, with "/docs": http://127.0.0.1:8000/docs
"""

app = FastAPI()
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


# Route to input data and get data to plot, with a project given in input
@app.get("/plots/{project}")
def show_plots(project: str):
    df = data_workflow(project)
    return {"df to send to plot_workflow": df}


# Route to test giving an argument: change message basd in input
@app.get("/message/{msg}")
def change_msg(msg: str) -> dict:
    return {"message": f"Hello World custom: {msg}"}


@app.get("/market-orders/{project}")
def call_complex_market_orders_data_workflow(project: str):
    paths = complex_market_orders_data_workflow(project)
    return paths


@app.get("/plot-market-orders/{project}/{file_id}")
def plot_mo(project: str, file_id: str):
    csv_path = resolve_market_orders_csv_path(project, file_id)
    try:
        image_buffer = plot_market_orders(csv_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StreamingResponse(image_buffer, media_type="image/png")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
