from __future__ import annotations

import asyncio
import datetime

import httpx
import pytest

from src.rte.rte_client import (
    DEFAULT_RTE_TOKEN_URL,
    RteAuthConfig,
    RteBadRequestError,
    RteConsumptionClient,
)
from src.rte.consumption_api.rte_consumption_models import (
    ShortTermQueryType,
    ShortTermResponseType,
)


def _response_payload() -> dict:
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


def test_get_short_term_builds_expected_query_params_and_headers() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["auth_header"] = request.headers["Authorization"]
        captured["type"] = request.url.params.get("type", "")
        captured["start_date"] = request.url.params.get("start_date", "")
        captured["end_date"] = request.url.params.get("end_date", "")
        return httpx.Response(200, json=_response_payload())

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            client = RteConsumptionClient(
                auth=RteAuthConfig(access_token="known-token"),
                http_client=http_client,
            )
            response = await client.get_short_term(
                types=[
                    ShortTermQueryType.REALISED,
                    ShortTermQueryType.ID,
                    ShortTermQueryType.REALISED,
                ],
                start_date=datetime.datetime(2026, 3, 20, 0, 0, tzinfo=datetime.UTC),
                end_date=datetime.datetime(2026, 3, 21, 0, 0, tzinfo=datetime.UTC),
            )

        assert response.short_term[0].type == ShortTermResponseType.REALISED
        assert response.short_term[0].values[0].value == 52345

    asyncio.run(scenario())

    assert captured["method"] == "GET"
    assert captured["path"] == "/open_api/consumption/v1/short_term"
    assert captured["auth_header"] == "Bearer known-token"
    assert captured["type"] == "REALISED,ID"
    assert captured["start_date"] == "2026-03-20T00:00:00+00:00"
    assert captured["end_date"] == "2026-03-21T00:00:00+00:00"


def test_get_short_term_raises_when_only_one_date_is_provided() -> None:
    async def scenario() -> None:
        async with RteConsumptionClient(
            auth=RteAuthConfig(access_token="known-token")
        ) as client:
            with pytest.raises(ValueError, match="must either both be filled in"):
                await client.get_short_term(
                    start_date=datetime.datetime(
                        2026, 3, 20, 0, 0, tzinfo=datetime.UTC
                    ),
                    end_date=None,
                )

    asyncio.run(scenario())


def test_get_short_term_raises_when_datetime_is_naive() -> None:
    async def scenario() -> None:
        async with RteConsumptionClient(
            auth=RteAuthConfig(access_token="known-token")
        ) as client:
            with pytest.raises(ValueError, match="must include timezone"):
                await client.get_short_term(
                    start_date=datetime.datetime(2026, 3, 20, 0, 0),
                    end_date=datetime.datetime(2026, 3, 21, 0, 0),
                )

    asyncio.run(scenario())


def test_get_short_term_fetches_oauth_token_with_client_credentials() -> None:
    captured_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_paths.append(request.url.path)
        if request.url.path == "/token/oauth/":
            assert request.method == "POST"
            assert request.headers["Authorization"].startswith("Basic ")
            assert request.headers["Content-Type"].startswith(
                "application/x-www-form-urlencoded"
            )
            return httpx.Response(
                200, json={"access_token": "issued-token", "expires_in": 7200}
            )

        if request.url.path == "/open_api/consumption/v1/short_term":
            assert request.headers["Authorization"] == "Bearer issued-token"
            return httpx.Response(200, json=_response_payload())

        return httpx.Response(404, json={"error": "unexpected path"})

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            client = RteConsumptionClient(
                auth=RteAuthConfig(
                    client_id="client-id",
                    client_secret="client-secret",
                    token_url=DEFAULT_RTE_TOKEN_URL,
                ),
                http_client=http_client,
            )
            await client.get_short_term(types=[ShortTermQueryType.REALISED])

    asyncio.run(scenario())

    assert captured_paths == ["/token/oauth/", "/open_api/consumption/v1/short_term"]


def test_get_short_term_fetches_oauth_token_with_precomputed_basic_auth() -> None:
    captured_authorization_headers: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token/oauth/":
            captured_authorization_headers.append(request.headers["Authorization"])
            return httpx.Response(200, json={"access_token": "issued-token"})
        if request.url.path == "/open_api/consumption/v1/short_term":
            return httpx.Response(200, json=_response_payload())
        return httpx.Response(404, json={"error": "unexpected path"})

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            client = RteConsumptionClient(
                auth=RteAuthConfig(
                    basic_authorization_b64="ZmFrZS1iYXNlNjQ=",
                    token_url=DEFAULT_RTE_TOKEN_URL,
                ),
                http_client=http_client,
            )
            await client.get_short_term(types=[ShortTermQueryType.REALISED])

    asyncio.run(scenario())

    assert captured_authorization_headers == ["Basic ZmFrZS1iYXNlNjQ="]


def test_get_short_term_maps_http_400_to_bad_request_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": "CONSUMPTION_SHORTTERM_F07",
                "error_description": (
                    "One of the enumerated field does not match with the list of expected values."
                ),
            },
        )

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            client = RteConsumptionClient(
                auth=RteAuthConfig(access_token="known-token"),
                http_client=http_client,
            )
            with pytest.raises(RteBadRequestError, match="enumerated field"):
                await client.get_short_term(types=[ShortTermQueryType.REALISED])

    asyncio.run(scenario())
