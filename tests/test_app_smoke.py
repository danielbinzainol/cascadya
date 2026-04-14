from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from fastapi.testclient import TestClient

import src.connection_aeolus_api as aeolus_api
from src.ml_models.api.main import app


def _write_market_orders_csv(path: Path) -> None:
    frame = pd.DataFrame(
        {
            "asset_id": ["inariz", "inariz"],
            "Delivery_datetime(UTC_start_of_period)": [
                "2026-02-11 00:00:00",
                "2026-02-11 00:15:00",
            ],
            "Price_min(E_MWh)": [-500.0, -500.0],
            "Price_max(E_MWh)": [58.0, 58.0],
            "Power_in_kW(Sell)": [-150.0, -300.0],
        }
    )
    frame.to_csv(path, sep=";", index=False)


def test_main_app_smoke_docs_forecast_and_aeolus_publish(monkeypatch, tmp_path) -> None:
    csv_path = tmp_path / "inariz_20260211_20260223_1735.csv"
    _write_market_orders_csv(csv_path)

    class FakeAeolusClient:
        def __init__(self, *, base_url: str, auth: object) -> None:
            _ = (base_url, auth)

        async def __aenter__(self) -> "FakeAeolusClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

        async def create_farm_cleared_volumes(self, payload):  # noqa: ANN001
            _ = payload
            return SimpleNamespace(transaction_ids=[11, 12])

    monkeypatch.setattr(
        aeolus_api,
        "_resolve_publish_csv_paths",
        lambda _project, _file_ids: [csv_path],
    )
    monkeypatch.setattr(aeolus_api, "AeolusClient", FakeAeolusClient)

    client = TestClient(app)
    with client:
        docs_response = client.get("/docs")
        assert docs_response.status_code == 200
        assert "text/html" in docs_response.headers["content-type"]

        forecasts_response = client.get("/forecasts/sites")
        assert forecasts_response.status_code == 200
        assert "sites" in forecasts_response.json()

        publish_response = client.post(
            "/aeolus/publish-market-orders/inariz",
            json={
                "farm_id": 777,
                "auth": {"access_token": "token-value"},
            },
        )
        assert publish_response.status_code == 200
        payload = publish_response.json()
        assert payload["transactions_submitted"] == 2
        assert payload["transaction_ids"] == [11, 12]
