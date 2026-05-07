from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from fastapi.testclient import TestClient

import src.connection_aeolus_api
from src.backoffice.api import main as backoffice_main

app = backoffice_main.app


def _disable_forecast_startup_db(monkeypatch) -> None:
    async def _noop_start() -> None:
        return None

    async def _noop_stop() -> None:
        return None

    monkeypatch.setattr(backoffice_main.FORECAST_MANAGER, "start", _noop_start)
    monkeypatch.setattr(backoffice_main.FORECAST_MANAGER, "stop", _noop_stop)


def _write_market_orders_csv(path: Path, *, power_kw_sell: list[float]) -> None:
    rows = len(power_kw_sell)
    frame = pd.DataFrame(
        {
            "asset_id": ["inariz"] * rows,
            "Delivery_datetime(UTC_start_of_period)": [
                "2026-02-11 00:00:00",
                "2026-02-11 00:15:00",
            ][:rows],
            "Price_min(E_MWh)": [-500.0] * rows,
            "Price_max(E_MWh)": [58.0] * rows,
            "Power_in_kW(Sell)": power_kw_sell,
        }
    )
    frame.to_csv(path, sep=";", index=False)


def test_publish_market_orders_endpoint_publishes_transactions(
    monkeypatch, tmp_path
) -> None:
    _disable_forecast_startup_db(monkeypatch)
    csv_path = tmp_path / "inariz_20260211_20260223_1735.csv"
    _write_market_orders_csv(csv_path, power_kw_sell=[-150.0, -300.0])
    captured: dict[str, int] = {}

    class FakeAeolusClient:
        def __init__(self, *, base_url: str, auth: object) -> None:
            captured["base_url_set"] = int(bool(base_url))
            captured["auth_set"] = int(bool(auth))

        async def __aenter__(self) -> "FakeAeolusClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

        async def create_farm_cleared_volumes(self, payload):  # noqa: ANN001
            captured["transaction_count"] = len(payload.transactions)
            return SimpleNamespace(transaction_ids=[11, 12])

    monkeypatch.setattr(
        src.connection_aeolus_api,
        "_resolve_publish_csv_paths",
        lambda _project, _file_ids: [csv_path],
    )
    monkeypatch.setattr(src.connection_aeolus_api, "AeolusClient", FakeAeolusClient)

    client = TestClient(app)
    with client:
        response = client.post(
            "/aeolus/publish-market-orders/inariz",
            json={
                "farm_id": 777,
                "auth": {"access_token": "token-value"},
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["transactions_submitted"] == 2
    assert payload["transaction_ids"] == [11, 12]
    assert payload["source_files"] == [str(csv_path)]
    assert captured["transaction_count"] == 2
    assert captured["base_url_set"] == 1
    assert captured["auth_set"] == 1


def test_publish_market_orders_endpoint_rejects_empty_publish(
    monkeypatch, tmp_path
) -> None:
    _disable_forecast_startup_db(monkeypatch)
    csv_path = tmp_path / "inariz_20260211_20260223_1735.csv"
    _write_market_orders_csv(csv_path, power_kw_sell=[0.0, 0.0])

    monkeypatch.setattr(
        src.connection_aeolus_api,
        "_resolve_publish_csv_paths",
        lambda _project, _file_ids: [csv_path],
    )

    client = TestClient(app)
    with client:
        response = client.post(
            "/aeolus/publish-market-orders/inariz",
            json={
                "farm_id": 777,
                "auth": {"access_token": "token-value"},
            },
        )

    assert response.status_code == 400
    assert "No publishable market orders found" in response.json()["detail"]
