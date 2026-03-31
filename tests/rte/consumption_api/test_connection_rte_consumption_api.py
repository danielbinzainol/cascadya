from __future__ import annotations

import datetime

from fastapi.testclient import TestClient

import src.rte.consumption_api.connection_rte_consumption_api
from src.rte.rte_client import RteAuthError
from src.rte.consumption_api.rte_consumption_models import ShortTermResponse


def _short_term_payload() -> dict:
    return {
        "short_term": [
            {
                "type": "REALISED",
                "start_date": "2026-03-20T00:00:00+01:00",
                "end_date": "2026-03-21T00:00:00+01:00",
                "values": [
                    {
                        "start_date": "2026-03-20T00:00:00+01:00",
                        "end_date": "2026-03-20T00:15:00+01:00",
                        "updated_date": "2026-03-20T00:20:00+01:00",
                        "value": 52345,
                    }
                ],
            }
        ]
    }


def test_rte_short_term_endpoint_calls_client_with_env_config(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeRteConsumptionClient:
        def __init__(self, *, base_url: str, auth: object) -> None:
            captured["base_url"] = base_url
            captured["access_token"] = getattr(auth, "access_token", None)

        async def __aenter__(self) -> "FakeRteConsumptionClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

        async def get_short_term(self, *, types, start_date, end_date):  # noqa: ANN001
            captured["types"] = [item.value for item in types] if types else []
            captured["start_date"] = start_date
            captured["end_date"] = end_date
            return ShortTermResponse.model_validate(_short_term_payload())

    monkeypatch.setattr(
        src.rte.consumption_api.connection_rte_consumption_api,
        "RteConsumptionClient",
        FakeRteConsumptionClient,
    )
    monkeypatch.setenv(
        "RTE_CONSUMPTION_BASE_URL", "https://custom-rte-host/open_api/consumption/v1"
    )
    monkeypatch.setenv("RTE_ACCESS_TOKEN", "rte-token-value")

    client = TestClient(src.rte.consumption_api.connection_rte_consumption_api.app)
    response = client.get(
        "/rte/consumption/short-term",
        params=[
            ("type", "REALISED"),
            ("type", "ID"),
            ("start_date", "2026-03-20T00:00:00+00:00"),
            ("end_date", "2026-03-21T00:00:00+00:00"),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["short_term"][0]["type"] == "REALISED"
    assert captured["base_url"] == "https://custom-rte-host/open_api/consumption/v1"
    assert captured["access_token"].get_secret_value() == "rte-token-value"
    assert captured["types"] == ["REALISED", "ID"]
    assert captured["start_date"] == datetime.datetime(
        2026, 3, 20, 0, 0, tzinfo=datetime.UTC
    )
    assert captured["end_date"] == datetime.datetime(
        2026, 3, 21, 0, 0, tzinfo=datetime.UTC
    )


def test_rte_short_term_endpoint_rejects_missing_env_credentials(monkeypatch) -> None:
    monkeypatch.delenv("RTE_CLIENT_ID", raising=False)
    monkeypatch.delenv("RTE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("RTE_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("RTE_BASIC_AUTH_B64", raising=False)
    monkeypatch.delenv("RTE_VAULT_ADDR", raising=False)
    monkeypatch.delenv("RTE_VAULT_TOKEN", raising=False)
    monkeypatch.delenv("RTE_VAULT_SECRET_PATH", raising=False)
    monkeypatch.delenv("VAULT_ADDR", raising=False)
    monkeypatch.delenv("VAULT_TOKEN", raising=False)

    client = TestClient(src.rte.consumption_api.connection_rte_consumption_api.app)
    response = client.get("/rte/consumption/short-term")

    assert response.status_code == 400
    assert "Missing RTE credentials" in response.json()["detail"]


def test_rte_short_term_endpoint_accepts_shared_basic_auth_b64(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeRteConsumptionClient:
        def __init__(self, *, base_url: str, auth: object) -> None:
            captured["base_url"] = base_url
            captured["basic_authorization_b64"] = getattr(
                auth, "basic_authorization_b64", None
            )

        async def __aenter__(self) -> "FakeRteConsumptionClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

        async def get_short_term(self, *, types, start_date, end_date):  # noqa: ANN001
            _ = (types, start_date, end_date)
            return ShortTermResponse.model_validate(_short_term_payload())

    monkeypatch.setattr(
        src.rte.consumption_api.connection_rte_consumption_api,
        "RteConsumptionClient",
        FakeRteConsumptionClient,
    )
    monkeypatch.delenv("RTE_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("RTE_CLIENT_ID", raising=False)
    monkeypatch.delenv("RTE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("RTE_VAULT_ADDR", raising=False)
    monkeypatch.delenv("RTE_VAULT_TOKEN", raising=False)
    monkeypatch.delenv("RTE_VAULT_SECRET_PATH", raising=False)
    monkeypatch.setenv("RTE_BASIC_AUTH_B64", "ZmFrZS1iYXNlNjQ=")

    client = TestClient(src.rte.consumption_api.connection_rte_consumption_api.app)
    response = client.get("/rte/consumption/short-term")

    assert response.status_code == 200
    assert captured["basic_authorization_b64"].get_secret_value() == "ZmFrZS1iYXNlNjQ="


def test_rte_short_term_endpoint_maps_auth_error(monkeypatch) -> None:
    class FakeRteConsumptionClient:
        def __init__(self, *, base_url: str, auth: object) -> None:
            _ = (base_url, auth)

        async def __aenter__(self) -> "FakeRteConsumptionClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

        async def get_short_term(self, *, types, start_date, end_date):  # noqa: ANN001
            _ = (types, start_date, end_date)
            raise RteAuthError("invalid token", status_code=401)

    monkeypatch.setattr(
        src.rte.consumption_api.connection_rte_consumption_api,
        "RteConsumptionClient",
        FakeRteConsumptionClient,
    )
    monkeypatch.setenv("RTE_ACCESS_TOKEN", "rte-token-value")

    client = TestClient(src.rte.consumption_api.connection_rte_consumption_api.app)
    response = client.get("/rte/consumption/short-term")

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid token"
