from __future__ import annotations

import datetime

from fastapi.testclient import TestClient

import src.rte.generation_forecast_api.connection_rte_generation_forecast_api
from src.rte.rte_client import RteAuthError
from src.rte.generation_forecast_api.rte_generation_forecast_models import (
    GenerationForecastResponse,
)


def _forecasts_payload() -> dict:
    return {
        "forecasts": [
            {
                "production_type": "WIND",
                "type": "D-1",
                "start_date": "2026-03-20T00:00:00+01:00",
                "end_date": "2026-03-21T00:00:00+01:00",
                "values": [
                    {
                        "start_date": "2026-03-20T00:00:00+01:00",
                        "end_date": "2026-03-20T00:15:00+01:00",
                        "updated_date": "2026-03-20T00:20:00+01:00",
                        "value": 2450,
                    }
                ],
            }
        ]
    }


def _total_forecast_payload() -> dict:
    return {
        "total_forecast": [
            {
                "type": "D-1",
                "start_date": "2026-03-20T00:00:00+01:00",
                "end_date": "2026-03-21T00:00:00+01:00",
                "values": [
                    {
                        "start_date": "2026-03-20T00:00:00+01:00",
                        "end_date": "2026-03-20T00:15:00+01:00",
                        "updated_date": "2026-03-20T00:20:00+01:00",
                        "value": 12150,
                    }
                ],
            }
        ]
    }


def test_generation_forecast_endpoint_calls_client_with_env_config(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeRteGenerationForecastClient:
        def __init__(self, *, base_url: str, auth: object) -> None:
            captured["base_url"] = base_url
            captured["access_token"] = getattr(auth, "access_token", None)

        async def __aenter__(self) -> "FakeRteGenerationForecastClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

        async def get_forecasts(
            self, *, production_types, forecast_types, start_date, end_date
        ):  # noqa: ANN001
            captured["production_types"] = production_types
            captured["forecast_types"] = forecast_types
            captured["start_date"] = start_date
            captured["end_date"] = end_date
            return GenerationForecastResponse.model_validate(_forecasts_payload())

    monkeypatch.setattr(
        src.rte.generation_forecast_api.connection_rte_generation_forecast_api,
        "RteGenerationForecastClient",
        FakeRteGenerationForecastClient,
    )
    monkeypatch.setenv(
        "RTE_GENERATION_FORECAST_BASE_URL",
        "https://custom-rte-host/open_api/generation_forecast/v3",
    )
    monkeypatch.setenv("RTE_ACCESS_TOKEN", "rte-token-value")

    client = TestClient(
        src.rte.generation_forecast_api.connection_rte_generation_forecast_api.app
    )
    response = client.get(
        "/rte/generation-forecast/forecasts",
        params=[
            ("production_type", "WIND"),
            ("production_type", "SOLAR"),
            ("type", "D-1"),
            ("type", "ID"),
            ("start_date", "2026-03-20T00:00:00+00:00"),
            ("end_date", "2026-03-21T00:00:00+00:00"),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["forecasts"][0]["production_type"] == "WIND"
    assert (
        captured["base_url"]
        == "https://custom-rte-host/open_api/generation_forecast/v3"
    )
    assert captured["access_token"].get_secret_value() == "rte-token-value"
    assert captured["production_types"] == ["WIND", "SOLAR"]
    assert captured["forecast_types"] == ["D-1", "ID"]
    assert captured["start_date"] == datetime.datetime(
        2026, 3, 20, 0, 0, tzinfo=datetime.UTC
    )
    assert captured["end_date"] == datetime.datetime(
        2026, 3, 21, 0, 0, tzinfo=datetime.UTC
    )


def test_generation_forecast_endpoint_rejects_missing_env_credentials(
    monkeypatch,
) -> None:
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
        src.rte.generation_forecast_api.connection_rte_generation_forecast_api.app
    )
    response = client.get("/rte/generation-forecast/forecasts")

    assert response.status_code == 400
    assert "Missing RTE credentials" in response.json()["detail"]


def test_generation_forecast_endpoint_accepts_shared_basic_auth_b64(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeRteGenerationForecastClient:
        def __init__(self, *, base_url: str, auth: object) -> None:
            captured["base_url"] = base_url
            captured["basic_authorization_b64"] = getattr(
                auth, "basic_authorization_b64", None
            )

        async def __aenter__(self) -> "FakeRteGenerationForecastClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

        async def get_forecasts(
            self, *, production_types, forecast_types, start_date, end_date
        ):  # noqa: ANN001
            _ = (production_types, forecast_types, start_date, end_date)
            return GenerationForecastResponse.model_validate(_forecasts_payload())

    monkeypatch.setattr(
        src.rte.generation_forecast_api.connection_rte_generation_forecast_api,
        "RteGenerationForecastClient",
        FakeRteGenerationForecastClient,
    )
    monkeypatch.delenv("RTE_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("RTE_CLIENT_ID", raising=False)
    monkeypatch.delenv("RTE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("RTE_VAULT_ADDR", raising=False)
    monkeypatch.delenv("RTE_VAULT_TOKEN", raising=False)
    monkeypatch.delenv("RTE_VAULT_SECRET_PATH", raising=False)
    monkeypatch.setenv("RTE_BASIC_AUTH_B64", "ZmFrZS1iYXNlNjQ=")

    client = TestClient(
        src.rte.generation_forecast_api.connection_rte_generation_forecast_api.app
    )
    response = client.get("/rte/generation-forecast/forecasts")

    assert response.status_code == 200
    assert captured["basic_authorization_b64"].get_secret_value() == "ZmFrZS1iYXNlNjQ="


def test_generation_forecast_endpoint_maps_auth_error(monkeypatch) -> None:
    class FakeRteGenerationForecastClient:
        def __init__(self, *, base_url: str, auth: object) -> None:
            _ = (base_url, auth)

        async def __aenter__(self) -> "FakeRteGenerationForecastClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

        async def get_forecasts(
            self, *, production_types, forecast_types, start_date, end_date
        ):  # noqa: ANN001
            _ = (production_types, forecast_types, start_date, end_date)
            raise RteAuthError("invalid token", status_code=401)

    monkeypatch.setattr(
        src.rte.generation_forecast_api.connection_rte_generation_forecast_api,
        "RteGenerationForecastClient",
        FakeRteGenerationForecastClient,
    )
    monkeypatch.setenv("RTE_ACCESS_TOKEN", "rte-token-value")

    client = TestClient(
        src.rte.generation_forecast_api.connection_rte_generation_forecast_api.app
    )
    response = client.get("/rte/generation-forecast/forecasts")

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid token"


def test_generation_total_forecast_endpoint_calls_client_with_env_config(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeRteGenerationForecastClient:
        def __init__(self, *, base_url: str, auth: object) -> None:
            captured["base_url"] = base_url
            captured["access_token"] = getattr(auth, "access_token", None)

        async def __aenter__(self) -> "FakeRteGenerationForecastClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

        async def get_total_forecast(self, *, forecast_types, start_date, end_date):  # noqa: ANN001
            captured["forecast_types"] = forecast_types
            captured["start_date"] = start_date
            captured["end_date"] = end_date
            from src.rte.generation_forecast_api.rte_generation_forecast_models import (
                TotalForecastResponse,
            )

            return TotalForecastResponse.model_validate(_total_forecast_payload())

    monkeypatch.setattr(
        src.rte.generation_forecast_api.connection_rte_generation_forecast_api,
        "RteGenerationForecastClient",
        FakeRteGenerationForecastClient,
    )
    monkeypatch.setenv(
        "RTE_GENERATION_FORECAST_BASE_URL",
        "https://custom-rte-host/open_api/generation_forecast/v3",
    )
    monkeypatch.setenv("RTE_ACCESS_TOKEN", "rte-token-value")

    client = TestClient(
        src.rte.generation_forecast_api.connection_rte_generation_forecast_api.app
    )
    response = client.get(
        "/rte/generation-forecast/total-forecast",
        params=[
            ("type", "D-1"),
            ("type", "ID"),
            ("start_date", "2026-03-20T00:00:00+00:00"),
            ("end_date", "2026-03-21T00:00:00+00:00"),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_forecast"][0]["type"] == "D-1"
    assert (
        captured["base_url"]
        == "https://custom-rte-host/open_api/generation_forecast/v3"
    )
    assert captured["access_token"].get_secret_value() == "rte-token-value"
    assert captured["forecast_types"] == ["D-1", "ID"]
    assert captured["start_date"] == datetime.datetime(
        2026, 3, 20, 0, 0, tzinfo=datetime.UTC
    )
    assert captured["end_date"] == datetime.datetime(
        2026, 3, 21, 0, 0, tzinfo=datetime.UTC
    )


def test_generation_total_forecast_endpoint_maps_auth_error(monkeypatch) -> None:
    class FakeRteGenerationForecastClient:
        def __init__(self, *, base_url: str, auth: object) -> None:
            _ = (base_url, auth)

        async def __aenter__(self) -> "FakeRteGenerationForecastClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

        async def get_total_forecast(self, *, forecast_types, start_date, end_date):  # noqa: ANN001
            _ = (forecast_types, start_date, end_date)
            raise RteAuthError("invalid token", status_code=401)

    monkeypatch.setattr(
        src.rte.generation_forecast_api.connection_rte_generation_forecast_api,
        "RteGenerationForecastClient",
        FakeRteGenerationForecastClient,
    )
    monkeypatch.setenv("RTE_ACCESS_TOKEN", "rte-token-value")

    client = TestClient(
        src.rte.generation_forecast_api.connection_rte_generation_forecast_api.app
    )
    response = client.get("/rte/generation-forecast/total-forecast")

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid token"
