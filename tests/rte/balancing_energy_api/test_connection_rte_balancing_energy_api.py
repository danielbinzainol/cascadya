from __future__ import annotations

import datetime

from fastapi.testclient import TestClient

import src.rte.balancing_energy_api.connection_rte_balancing_energy_api
from src.rte.rte_client import RteAuthError
from src.rte.balancing_energy_api.rte_balancing_energy_models import (
    ImbalanceDataResponse,
)


def _imbalance_data_payload() -> dict:
    return {
        "imbalance_data": [
            {
                "start_date": "2026-03-20T00:00:00+01:00",
                "end_date": "2026-03-21T00:00:00+01:00",
                "resolution": "PT15M",
                "values": [
                    {
                        "start_date": "2026-03-20T00:00:00+01:00",
                        "end_date": "2026-03-20T00:15:00+01:00",
                        "imbalance": 200,
                        "system_trend": "Hausse",
                        "positive_imbalance_settlement_price": 45.55,
                        "negative_imbalance_settlement_price": 42.27,
                        "missing_data_list": "none",
                        "updated_date": "2026-03-20T00:30:00+01:00",
                    }
                ],
            }
        ]
    }


def test_imbalance_data_endpoint_calls_client_with_env_config(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeRteBalancingEnergyClient:
        def __init__(self, *, base_url: str, auth: object) -> None:
            captured["base_url"] = base_url
            captured["access_token"] = getattr(auth, "access_token", None)

        async def __aenter__(self) -> "FakeRteBalancingEnergyClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

        async def get_imbalance_data(self, *, start_date, end_date):  # noqa: ANN001
            captured["start_date"] = start_date
            captured["end_date"] = end_date
            return ImbalanceDataResponse.model_validate(_imbalance_data_payload())

    monkeypatch.setattr(
        src.rte.balancing_energy_api.connection_rte_balancing_energy_api,
        "RteBalancingEnergyClient",
        FakeRteBalancingEnergyClient,
    )
    monkeypatch.setenv(
        "RTE_BALANCING_ENERGY_BASE_URL",
        "https://custom-rte-host/open_api/balancing_energy/v5",
    )
    monkeypatch.setenv("RTE_ACCESS_TOKEN", "rte-token-value")

    client = TestClient(
        src.rte.balancing_energy_api.connection_rte_balancing_energy_api.app
    )
    response = client.get(
        "/rte/balancing-energy/imbalance-data",
        params=[
            ("start_date", "2026-03-20T00:00:00+00:00"),
            ("end_date", "2026-03-21T00:00:00+00:00"),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["imbalance_data"][0]["resolution"] == "PT15M"
    assert (
        captured["base_url"] == "https://custom-rte-host/open_api/balancing_energy/v5"
    )
    assert captured["access_token"].get_secret_value() == "rte-token-value"
    assert captured["start_date"] == datetime.datetime(
        2026, 3, 20, 0, 0, tzinfo=datetime.UTC
    )
    assert captured["end_date"] == datetime.datetime(
        2026, 3, 21, 0, 0, tzinfo=datetime.UTC
    )


def test_imbalance_data_endpoint_rejects_missing_env_credentials(monkeypatch) -> None:
    monkeypatch.delenv("RTE_CLIENT_ID", raising=False)
    monkeypatch.delenv("RTE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("RTE_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("RTE_BASIC_AUTH_B64", raising=False)
    monkeypatch.delenv("RTE_VAULT_ADDR", raising=False)
    monkeypatch.delenv("RTE_VAULT_TOKEN", raising=False)
    monkeypatch.delenv("RTE_VAULT_SECRET_PATH", raising=False)
    monkeypatch.delenv("VAULT_ADDR", raising=False)
    monkeypatch.delenv("VAULT_TOKEN", raising=False)

    client = TestClient(
        src.rte.balancing_energy_api.connection_rte_balancing_energy_api.app
    )
    response = client.get("/rte/balancing-energy/imbalance-data")

    assert response.status_code == 400
    assert "Missing RTE credentials" in response.json()["detail"]


def test_imbalance_data_endpoint_accepts_shared_basic_auth_b64(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeRteBalancingEnergyClient:
        def __init__(self, *, base_url: str, auth: object) -> None:
            captured["base_url"] = base_url
            captured["basic_authorization_b64"] = getattr(
                auth, "basic_authorization_b64", None
            )

        async def __aenter__(self) -> "FakeRteBalancingEnergyClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

        async def get_imbalance_data(self, *, start_date, end_date):  # noqa: ANN001
            _ = (start_date, end_date)
            return ImbalanceDataResponse.model_validate(_imbalance_data_payload())

    monkeypatch.setattr(
        src.rte.balancing_energy_api.connection_rte_balancing_energy_api,
        "RteBalancingEnergyClient",
        FakeRteBalancingEnergyClient,
    )
    monkeypatch.delenv("RTE_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("RTE_CLIENT_ID", raising=False)
    monkeypatch.delenv("RTE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("RTE_VAULT_ADDR", raising=False)
    monkeypatch.delenv("RTE_VAULT_TOKEN", raising=False)
    monkeypatch.delenv("RTE_VAULT_SECRET_PATH", raising=False)
    monkeypatch.setenv("RTE_BASIC_AUTH_B64", "ZmFrZS1iYXNlNjQ=")

    client = TestClient(
        src.rte.balancing_energy_api.connection_rte_balancing_energy_api.app
    )
    response = client.get("/rte/balancing-energy/imbalance-data")

    assert response.status_code == 200
    assert captured["basic_authorization_b64"].get_secret_value() == "ZmFrZS1iYXNlNjQ="


def test_imbalance_data_endpoint_maps_auth_error(monkeypatch) -> None:
    class FakeRteBalancingEnergyClient:
        def __init__(self, *, base_url: str, auth: object) -> None:
            _ = (base_url, auth)

        async def __aenter__(self) -> "FakeRteBalancingEnergyClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

        async def get_imbalance_data(self, *, start_date, end_date):  # noqa: ANN001
            _ = (start_date, end_date)
            raise RteAuthError("invalid token", status_code=401)

    monkeypatch.setattr(
        src.rte.balancing_energy_api.connection_rte_balancing_energy_api,
        "RteBalancingEnergyClient",
        FakeRteBalancingEnergyClient,
    )
    monkeypatch.setenv("RTE_ACCESS_TOKEN", "rte-token-value")

    client = TestClient(
        src.rte.balancing_energy_api.connection_rte_balancing_energy_api.app
    )
    response = client.get("/rte/balancing-energy/imbalance-data")

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid token"
