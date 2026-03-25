from __future__ import annotations

import base64
import datetime
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import SecretStr

from src.rte.balancing_energy_api.rte_balancing_energy_models import ImbalanceDataResponse
from src.rte.consumption_api.rte_consumption_models import RteApiErrorPayload

DEFAULT_RTE_BALANCING_ENERGY_BASE_URL = "https://digital.iservices.rte-france.com/open_api/balancing_energy/v5"
DEFAULT_RTE_TOKEN_URL = "https://digital.iservices.rte-france.com/token/oauth/"


class RteBalancingEnergyApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int, payload: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class RteBalancingEnergyAuthError(RteBalancingEnergyApiError):
    pass


class RteBalancingEnergyForbiddenError(RteBalancingEnergyApiError):
    pass


class RteBalancingEnergyNotFoundError(RteBalancingEnergyApiError):
    pass


class RteBalancingEnergyBadRequestError(RteBalancingEnergyApiError):
    pass


class RteBalancingEnergyRateLimitError(RteBalancingEnergyApiError):
    pass


@dataclass(slots=True)
class RteBalancingEnergyAuthConfig:
    access_token: SecretStr | str | None = None
    client_id: str | None = None
    client_secret: SecretStr | str | None = None
    basic_authorization_b64: SecretStr | str | None = None
    token_url: str = DEFAULT_RTE_TOKEN_URL
    token_timeout_seconds: float = 20.0

    def __post_init__(self) -> None:
        self.access_token = _ensure_secret(self.access_token)
        self.client_secret = _ensure_secret(self.client_secret)
        self.basic_authorization_b64 = _ensure_secret(self.basic_authorization_b64)


@dataclass(slots=True)
class _BearerToken:
    access_token: str
    expires_at: datetime.datetime | None = None

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.datetime.now(tz=datetime.UTC) >= self.expires_at


def _ensure_secret(value: SecretStr | str | None) -> SecretStr | None:
    if value is None:
        return None
    if isinstance(value, SecretStr):
        return value
    return SecretStr(value)


class RteBalancingEnergyClient:
    def __init__(
        self,
        *,
        auth: RteBalancingEnergyAuthConfig,
        base_url: str = DEFAULT_RTE_BALANCING_ENERGY_BASE_URL,
        timeout_seconds: float = 30.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._auth = auth
        self._base_url = base_url.rstrip("/")
        self._http = http_client or httpx.AsyncClient(timeout=timeout_seconds)
        self._owns_http_client = http_client is None
        self._cached_token: _BearerToken | None = None

    async def __aenter__(self) -> RteBalancingEnergyClient:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_http_client:
            await self._http.aclose()

    async def get_imbalance_data(
        self,
        *,
        start_date: datetime.datetime | None = None,
        end_date: datetime.datetime | None = None,
    ) -> ImbalanceDataResponse:
        params: dict[str, str] = {}
        if start_date:
            params["start_date"] = self._datetime_to_api_format(start_date)
        if end_date:
            params["end_date"] = self._datetime_to_api_format(end_date)

        payload = await self._request("GET", "/imbalance_data", params=params or None)
        return ImbalanceDataResponse.model_validate(payload)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        expected_status: set[int] | None = None,
    ) -> Any:
        expected_status = expected_status or {200}
        token = await self._resolve_access_token()
        response = await self._http.request(
            method=method,
            url=f"{self._base_url}{path}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            params=params,
        )
        if response.status_code not in expected_status:
            self._raise_for_status(response)
        return response.json()

    def _datetime_to_api_format(self, value: datetime.datetime) -> str:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Datetime values sent to RTE must include timezone information.")
        return value.isoformat()

    async def _resolve_access_token(self) -> str:
        if self._cached_token and not self._cached_token.is_expired():
            return self._cached_token.access_token

        if self._auth.access_token:
            self._cached_token = _BearerToken(access_token=self._auth.access_token.get_secret_value())
            return self._cached_token.access_token

        has_basic_auth_b64 = bool(self._auth.basic_authorization_b64)
        has_client_credentials = bool(self._auth.client_id and self._auth.client_secret)
        if not has_basic_auth_b64 and not has_client_credentials:
            raise RteBalancingEnergyAuthError(
                "Missing RTE credentials: provide access_token, basic_authorization_b64, or client_id/client_secret.",
                status_code=401,
            )

        token = await self._fetch_client_credentials_token()
        self._cached_token = token
        return token.access_token

    async def _fetch_client_credentials_token(self) -> _BearerToken:
        basic_credentials = (
            self._auth.basic_authorization_b64.get_secret_value() if self._auth.basic_authorization_b64 else None
        )
        if not basic_credentials:
            basic_credentials = base64.b64encode(
                f"{self._auth.client_id}:{self._auth.client_secret.get_secret_value()}".encode("utf-8")
            ).decode("ascii")
        response = await self._http.post(
            self._auth.token_url,
            headers={
                "Authorization": f"Basic {basic_credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={},
            timeout=self._auth.token_timeout_seconds,
        )
        if response.status_code >= 400:
            self._raise_for_status(response)

        payload = response.json()
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise RteBalancingEnergyAuthError(
                "Token endpoint response did not include access_token.",
                status_code=401,
                payload=payload,
            )

        expires_at: datetime.datetime | None = None
        expires_in = payload.get("expires_in")
        if isinstance(expires_in, int):
            expires_at = datetime.datetime.now(tz=datetime.UTC) + datetime.timedelta(seconds=max(expires_in - 60, 0))
        return _BearerToken(access_token=access_token, expires_at=expires_at)

    def _raise_for_status(self, response: httpx.Response) -> None:
        status_code = response.status_code
        payload: Any
        message: str
        try:
            payload = response.json()
            parsed_payload = RteApiErrorPayload.model_validate(payload) if isinstance(payload, dict) else None
            if parsed_payload and parsed_payload.error_description:
                message = parsed_payload.error_description
            elif parsed_payload and parsed_payload.error:
                message = parsed_payload.error
            elif isinstance(payload, dict) and isinstance(payload.get("detail"), str):
                message = payload["detail"]
            else:
                message = f"RTE Balancing Energy API error {status_code}"
        except ValueError:
            payload = response.text
            message = payload if isinstance(payload, str) and payload else f"RTE Balancing Energy API error {status_code}"

        if status_code == 400:
            raise RteBalancingEnergyBadRequestError(message, status_code=status_code, payload=payload)
        if status_code == 401:
            raise RteBalancingEnergyAuthError(message, status_code=status_code, payload=payload)
        if status_code == 403:
            raise RteBalancingEnergyForbiddenError(message, status_code=status_code, payload=payload)
        if status_code == 404:
            raise RteBalancingEnergyNotFoundError(message, status_code=status_code, payload=payload)
        if status_code == 429:
            raise RteBalancingEnergyRateLimitError(message, status_code=status_code, payload=payload)
        raise RteBalancingEnergyApiError(message, status_code=status_code, payload=payload)
