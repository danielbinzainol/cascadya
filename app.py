import uvicorn

from src.market_orders_paths import resolve_market_orders_csv_path
from src.ml_models.api.main import app

__all__ = ["app", "resolve_market_orders_csv_path"]


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
