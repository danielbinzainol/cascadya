import uvicorn
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.connection_aeolus_api import router as aeolus_router
from src.backoffice.forecasts.manager import ForecastManager
from src.backoffice.forecasts.router import build_forecast_router
from src.backoffice.api.routers.admin_queries import router as admin_queries_router
from src.backoffice.api.routers.market_orders import router as market_orders_router

app = FastAPI()
STATIC_DIR = (Path(__file__).resolve().parents[3] / "static").resolve()
BACKOFFICE_HOME = STATIC_DIR / "backoffice" / "index.html"
FORECAST_MANAGER = ForecastManager(data_root=Path(__file__).resolve().parents[3])


@app.on_event("startup")
async def startup_forecasts() -> None:
    await FORECAST_MANAGER.start()


@app.on_event("shutdown")
async def shutdown_forecasts() -> None:
    await FORECAST_MANAGER.stop()


app.include_router(market_orders_router)
app.include_router(build_forecast_router(FORECAST_MANAGER))
app.include_router(admin_queries_router)
app.include_router(aeolus_router)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/backoffice")
def backoffice_home() -> FileResponse:
    if not BACKOFFICE_HOME.exists():
        raise HTTPException(status_code=500, detail="Backoffice home UI is missing.")
    return FileResponse(BACKOFFICE_HOME)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
