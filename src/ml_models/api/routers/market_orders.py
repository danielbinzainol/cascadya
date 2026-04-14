from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from plots import plot_market_orders
from src.market_orders import complex_market_orders_data_workflow
from src.market_orders_paths import resolve_market_orders_csv_path


router = APIRouter()


@router.get("/market-orders/{project}/{data_type}/{filename}")
def call_complex_market_orders_data_workflow(
    project: str, data_type: str, filename: str
):
    paths = complex_market_orders_data_workflow(project, data_type, filename)
    return paths


@router.get("/plot-market-orders/{project}/{file_id}")
def plot_mo(project: str, file_id: str):
    csv_path = resolve_market_orders_csv_path(project, file_id)
    try:
        image_buffer = plot_market_orders(csv_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StreamingResponse(image_buffer, media_type="image/png")
