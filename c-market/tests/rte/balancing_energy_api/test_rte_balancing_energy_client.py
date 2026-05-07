from __future__ import annotations

import asyncio
import datetime

import httpx
import pytest

from src.rte.rte_client import (
    DEFAULT_RTE_TOKEN_URL,
    RteAuthConfig,
    RteBadRequestError,
    RteBalancingEnergyClient,
)


def _response_payload() -> dict:
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


def test_get_imbalance_data_builds_expected_query_params_and_headers() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["auth_header"] = request.headers["Authorization"]
        captured["start_date"] = request.url.params.get("start_date", "")
        captured["end_date"] = request.url.params.get("end_date", "")
        return httpx.Response(200, json=_response_payload())

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            client = RteBalancingEnergyClient(
                auth=RteAuthConfig(access_token="known-token"),
                http_client=http_client,
            )
            response = await client.get_imbalance_data(
                start_date=datetime.datetime(2026, 3, 20, 0, 0, tzinfo=datetime.UTC),
                end_date=datetime.datetime(2026, 3, 21, 0, 0, tzinfo=datetime.UTC),
            )

        assert response.imbalance_data[0].values[0].imbalance == 200

    asyncio.run(scenario())

    assert captured["method"] == "GET"
    assert captured["path"] == "/open_api/balancing_energy/v5/imbalance_data"
    assert captured["auth_header"] == "Bearer known-token"
    assert captured["start_date"] == "2026-03-20T00:00:00+00:00"
    assert captured["end_date"] == "2026-03-21T00:00:00+00:00"


def test_get_imbalance_data_raises_when_datetime_is_naive() -> None:
    async def scenario() -> None:
        async with RteBalancingEnergyClient(
            auth=RteAuthConfig(access_token="known-token")
        ) as client:
            with pytest.raises(ValueError, match="must include timezone"):
                await client.get_imbalance_data(
                    start_date=datetime.datetime(2026, 3, 20, 0, 0),
                    end_date=datetime.datetime(2026, 3, 21, 0, 0),
                )

    asyncio.run(scenario())


def test_get_imbalance_data_fetches_oauth_token_with_precomputed_basic_auth() -> None:
    captured_authorization_headers: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token/oauth/":
            captured_authorization_headers.append(request.headers["Authorization"])
            return httpx.Response(200, json={"access_token": "issued-token"})
        if request.url.path == "/open_api/balancing_energy/v5/imbalance_data":
            return httpx.Response(200, json=_response_payload())
        return httpx.Response(404, json={"error": "unexpected path"})

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            client = RteBalancingEnergyClient(
                auth=RteAuthConfig(
                    basic_authorization_b64="ZmFrZS1iYXNlNjQ=",
                    token_url=DEFAULT_RTE_TOKEN_URL,
                ),
                http_client=http_client,
            )
            await client.get_imbalance_data()

    asyncio.run(scenario())

    assert captured_authorization_headers == ["Basic ZmFrZS1iYXNlNjQ="]


def test_get_imbalance_data_maps_http_400_to_bad_request_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": "BALANCING_ENERGY_F07",
                "error_description": "One of the enumerated field does not match with the list of expected values.",
            },
        )

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            client = RteBalancingEnergyClient(
                auth=RteAuthConfig(access_token="known-token"),
                http_client=http_client,
            )
            with pytest.raises(RteBadRequestError, match="enumerated field"):
                await client.get_imbalance_data()

    asyncio.run(scenario())
