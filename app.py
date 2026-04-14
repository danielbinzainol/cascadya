import uvicorn
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from src.ingest import data_workflow
from src.market_orders import complex_market_orders_data_workflow
from src.market_orders_paths import resolve_market_orders_csv_path
from src.forecast_backoffice import ForecastManager, build_forecast_router
from src.connection_aeolus_api import router as aeolus_router
from plots import plot_market_orders

"""
Use: run this file in debug mode, with F5.
Go to the local url, with "/docs": http://127.0.0.1:8000/docs
"""

app = FastAPI()
STATIC_DIR = (Path(__file__).resolve().parent / "static").resolve()
BACKOFFICE_HOME = STATIC_DIR / "backoffice" / "index.html"
FORECAST_MANAGER = ForecastManager(data_root=Path(__file__).resolve().parent)


# Route to input data and get data to plot, with a project given in input
@app.get("/plots/{project}/{data_type}/{filename}")
def show_plots(project: str, data_type: str, filename: str):
    df = data_workflow(project, data_type, filename)
    return {"df to send to plot_workflow": df}


# Route to test giving an argument: change message basd in input
@app.get("/message/{msg}")
def change_msg(msg: str) -> dict:
    return {"message": f"Hello World custom: {msg}"}


@app.get("/market-orders/{project}/{data_type}/{filename}")
def call_complex_market_orders_data_workflow(
    project: str, data_type: str, filename: str
):
    paths = complex_market_orders_data_workflow(project, data_type, filename)
    return paths


@app.get("/plot-market-orders/{project}/{file_id}")
def plot_mo(project: str, file_id: str):
    csv_path = resolve_market_orders_csv_path(project, file_id)
    try:
        image_buffer = plot_market_orders(csv_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StreamingResponse(image_buffer, media_type="image/png")


@app.on_event("startup")
async def startup_forecasts() -> None:
    await FORECAST_MANAGER.start()


@app.on_event("shutdown")
async def shutdown_forecasts() -> None:
    await FORECAST_MANAGER.stop()


app.include_router(build_forecast_router(FORECAST_MANAGER))
app.include_router(aeolus_router)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/backoffice")
def backoffice_home() -> FileResponse:
    if not BACKOFFICE_HOME.exists():
        raise HTTPException(status_code=500, detail="Backoffice home UI is missing.")
    return FileResponse(BACKOFFICE_HOME)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
