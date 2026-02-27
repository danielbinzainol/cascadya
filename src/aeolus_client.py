from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any

import httpx
from pydantic import TypeAdapter

from src.aeolus_models import (
    AllowedMarket,
    AllowedTransactionType,
    AssetModel,
    AssetPointsWithCreatedDate,
    AssetTimeSeriesPayload,
    AssetTimeSeriesResponse,
    FarmClearedVolumesRetrieveResponse,
    ForecastAssetPoints,
    ForecastVersion,
    ImbalancePriceResponse,
    LegacyTimeSeriesPayload,
    LegacyTimeSeriesResponse,
    Maintenance,
    MaintenancePayload,
    MaintenanceResponse,
    MarketFarmTransactionsCreate,
    MeteringRecordsCreateResponse,
    MeteringsCreateLegacy,
    MeteringsRecordsCreate,
    PortfolioTransactionsResponse,
    PortfoliosPayload,
    ProductTimeStep,
    ProductTimeStepApi,
    SpotPriceResponse,
    TransactionType,
    TransactionsCreateResponse,
    WeatherMeasurementsCreate,
    WeatherMeasurementsCreateResponse,
    WeatherMeteringPoints,
)

READ_ASSETS_SCOPE = "https://aeolus.main.e6-group.com/read:assets"
READ_ASSET_FORECAST_SCOPE = "https://aeolus.main.e6-group.com/read:asset:forecast"
WRITE_ASSET_FORECAST_SCOPE = "https://aeolus.main.e6-group.com/write:asset:forecast"
READ_ASSET_MAINTENANCE_SCOPE = "https://aeolus.main.e6-group.com/read:asset:maintenance"
WRITE_ASSET_MAINTENANCE_SCOPE = "https://aeolus.main.e6-group.com/write:asset:maintenance"
READ_ASSET_METER_SCOPE = "https://aeolus.main.e6-group.com/read:asset:meter"
WRITE_ASSET_METER_SCOPE = "https://aeolus.main.e6-group.com/write:asset:meter"
READ_PORTFOLIOS_SCOPE = "https://aeolus.main.e6-group.com/read:portfolios"
READ_MARKET_SCOPE = "https://aeolus.main.e6-group.com/read:market"
READ_TRANSACTIONS_SCOPE = "https://aeolus.main.e6-group.com/read:transactions"
READ_COUNTRIES_SCOPE = "https://aeolus.main.e6-group.com/read:countries"
READ_BPS_SCOPE = "https://aeolus.main.e6-group.com/read:bps"
READ_CONNECTION_POINT_SCOPE = "https://aeolus.main.e6-group.com/read:connection_point"
WRITE_CONNECTION_POINT_SCOPE = "https://aeolus.main.e6-group.com/write:connection_point"
WRITE_TRANSACTIONS_SCOPE = "https://aeolus.main.e6-group.com/write:transactions"
WRITE_METERING_SCOPE = "https://aeolus.main.e6-group.com/write:metering"
WRITE_WEATHER_MEASUREMENT_SCOPE = "https://aeolus.main.e6-group.com/write:weather_measurement"


class AeolusApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int, payload: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class AeolusForbiddenError(AeolusApiError):
    pass


class AeolusNotFoundError(AeolusApiError):
    pass


class AeolusValidationError(AeolusApiError):
    pass


class AeolusAuthError(AeolusApiError):
    pass


@dataclass(slots=True)
class AeolusAuthConfig:
    access_token: str | None = None
    allowed_scopes: set[str] = field(default_factory=set)
    token_url: str = "https://eole-api-gateway-prod.auth.eu-west-1.amazoncognito.com/oauth2/token"
    client_id: str | None = None
    client_secret: str | None = None
    token_scope: str | None = None
    token_timeout_seconds: float = 20.0


@dataclass(slots=True)
class _BearerToken:
    access_token: str
    expires_at: datetime.datetime | None = None
    scopes: set[str] = field(default_factory=set)

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.datetime.now(tz=datetime.UTC) >= self.expires_at


class AeolusClient:
    def __init__(
        self,
        *,
        base_url: str = "https://e6.aeolus.main.e6-group.com/api/v2",
        auth: AeolusAuthConfig,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth = auth
        self._http = httpx.AsyncClient(timeout=timeout_seconds)
        self._cached_token: _BearerToken | None = None

    async def __aenter__(self) -> AeolusClient:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await self._http.aclose()

    async def get_assets(self) -> dict[str, list[AssetModel]]:
        payload = await self._request("GET", "/assets", required_scopes={READ_ASSETS_SCOPE})
        return TypeAdapter(dict[str, list[AssetModel]]).validate_python(payload)

    async def get_asset_forecast(
        self,
        *,
        asset_id: int,
        start: datetime.datetime,
        end: datetime.datetime,
        version: ForecastVersion | None = None,
    ) -> ForecastAssetPoints:
        params: dict[str, Any] = {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "version": version.value if version else None,
        }
        payload = await self._request(
            "GET",
            f"/asset/{asset_id}/forecast",
            params=params,
            required_scopes={READ_ASSET_FORECAST_SCOPE},
        )
        return ForecastAssetPoints.model_validate(payload)

    async def create_asset_forecast(self, *, asset_id: int, body: AssetTimeSeriesPayload) -> AssetTimeSeriesResponse:
        payload = await self._request(
            "POST",
            f"/asset/{asset_id}/forecast",
            json=body.model_dump(by_alias=True, exclude_none=True),
            expected_status={201},
            required_scopes={WRITE_ASSET_FORECAST_SCOPE},
        )
        return AssetTimeSeriesResponse.model_validate(payload)

    async def get_asset_maintenance(
        self,
        *,
        asset_id: int,
        start: datetime.datetime | None = None,
        end: datetime.datetime | None = None,
    ) -> list[Maintenance]:
        params: dict[str, Any] = {
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
        }
        payload = await self._request(
            "GET",
            f"/asset/{asset_id}/maintenance",
            params=params,
            required_scopes={READ_ASSET_MAINTENANCE_SCOPE},
        )
        return TypeAdapter(list[Maintenance]).validate_python(payload)

    async def create_asset_maintenance(self, *, asset_id: int, body: MaintenancePayload) -> MaintenanceResponse:
        payload = await self._request(
            "POST",
            f"/asset/{asset_id}/maintenance",
            json=body.model_dump(by_alias=True, exclude_none=True),
            expected_status={201},
            required_scopes={WRITE_ASSET_MAINTENANCE_SCOPE},
        )
        return MaintenanceResponse.model_validate(payload)

    async def update_asset_maintenance(self, *, asset_id: int, maintenances: list[Maintenance]) -> None:
        await self._request(
            "PUT",
            f"/asset/{asset_id}/maintenance",
            json=[maintenance.model_dump(by_alias=True, exclude_none=True) for maintenance in maintenances],
            expected_status={204},
            required_scopes={WRITE_ASSET_MAINTENANCE_SCOPE},
        )

    async def delete_asset_maintenance(self, *, asset_id: int, maintenance_id: int) -> None:
        await self._request(
            "DELETE",
            f"/asset/{asset_id}/maintenance/{maintenance_id}",
            expected_status={204},
            required_scopes={WRITE_ASSET_MAINTENANCE_SCOPE},
        )

    async def get_asset_metering(
        self,
        *,
        asset_id: int,
        start: datetime.datetime | None = None,
        end: datetime.datetime | None = None,
        created_after: datetime.datetime | None = None,
        created_before: datetime.datetime | None = None,
    ) -> AssetPointsWithCreatedDate:
        params: dict[str, Any] = {
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
            "created_after": created_after.isoformat() if created_after else None,
            "created_before": created_before.isoformat() if created_before else None,
        }
        payload = await self._request(
            "GET",
            f"/asset/{asset_id}/metering",
            params=params,
            required_scopes={READ_ASSET_METER_SCOPE},
        )
        return AssetPointsWithCreatedDate.model_validate(payload)

    async def create_asset_metering(self, *, asset_id: int, body: AssetTimeSeriesPayload) -> AssetTimeSeriesResponse:
        payload = await self._request(
            "POST",
            f"/asset/{asset_id}/metering",
            json=body.model_dump(by_alias=True, exclude_none=True),
            expected_status={201},
            required_scopes={WRITE_ASSET_METER_SCOPE},
        )
        return AssetTimeSeriesResponse.model_validate(payload)

    async def get_asset_weather_metering(
        self,
        *,
        asset_id: int,
        start: datetime.datetime,
        end: datetime.datetime,
    ) -> WeatherMeteringPoints:
        params: dict[str, str] = {"start": start.isoformat(), "end": end.isoformat()}
        payload = await self._request(
            "GET",
            f"/asset/{asset_id}/weatherMetering",
            params=params,
            required_scopes={READ_ASSET_METER_SCOPE},
        )
        return WeatherMeteringPoints.model_validate(payload)

    async def get_portfolios(self) -> PortfoliosPayload:
        payload = await self._request(
            "GET",
            "/portfolios",
            required_scopes={READ_PORTFOLIOS_SCOPE},
        )
        return PortfoliosPayload.model_validate(payload)

    async def get_country_spot_prices(
        self,
        *,
        country: str,
        start: datetime.datetime,
        end: datetime.datetime,
        product_time_step_in: list[ProductTimeStep] | None = None,
    ) -> SpotPriceResponse:
        params: dict[str, Any] = {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "product_time_step_in": [step.value for step in product_time_step_in] if product_time_step_in else None,
        }
        payload = await self._request(
            "GET",
            f"/market/country/{country}/spot",
            params=params,
            required_scopes={READ_MARKET_SCOPE},
        )
        return SpotPriceResponse.model_validate(payload)

    async def get_country_imbalance_prices(
        self,
        *,
        country: str,
        start: datetime.datetime,
        end: datetime.datetime,
    ) -> ImbalancePriceResponse:
        payload = await self._request(
            "GET",
            f"/market/country/{country}/imbalancePrices",
            params={"start": start.isoformat(), "end": end.isoformat()},
            required_scopes={READ_MARKET_SCOPE},
        )
        return ImbalancePriceResponse.model_validate(payload)

    async def get_market_portfolio_transactions(
        self,
        *,
        portfolio_id: int,
        start: datetime.datetime,
        end: datetime.datetime,
        transaction_type: TransactionType | None = None,
    ) -> PortfolioTransactionsResponse:
        params: dict[str, Any] = {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "transaction_type": transaction_type.value if transaction_type else None,
        }
        payload = await self._request(
            "GET",
            f"/market/portfolio/{portfolio_id}/transactions",
            params=params,
            required_scopes={READ_TRANSACTIONS_SCOPE},
        )
        return PortfolioTransactionsResponse.model_validate(payload)

    async def get_countries(self) -> list[dict[str, Any]]:
        payload = await self._request("GET", "/countries", required_scopes={READ_COUNTRIES_SCOPE})
        return TypeAdapter(list[dict[str, Any]]).validate_python(payload)

    async def get_bps(self) -> list[dict[str, Any]]:
        payload = await self._request("GET", "/bps", required_scopes={READ_BPS_SCOPE})
        return TypeAdapter(list[dict[str, Any]]).validate_python(payload)

    async def get_connection_point_metering(
        self,
        *,
        connection_point_ean_code: str,
        start: datetime.datetime,
        end: datetime.datetime,
    ) -> LegacyTimeSeriesResponse:
        payload = await self._request(
            "GET",
            f"/connection-points/{connection_point_ean_code}/metering",
            params={"start": start.isoformat(), "end": end.isoformat()},
            required_scopes={READ_CONNECTION_POINT_SCOPE},
        )
        return LegacyTimeSeriesResponse.model_validate(payload)

    async def get_connection_point_forecast(
        self,
        *,
        connection_point_ean_code: str,
        start: datetime.datetime,
        end: datetime.datetime,
    ) -> LegacyTimeSeriesResponse:
        payload = await self._request(
            "GET",
            f"/connection-points/{connection_point_ean_code}/forecast",
            params={"start": start.isoformat(), "end": end.isoformat()},
            required_scopes={READ_CONNECTION_POINT_SCOPE},
        )
        return LegacyTimeSeriesResponse.model_validate(payload)

    async def create_connection_point_forecast(
        self,
        *,
        connection_point_ean_code: str,
        body: LegacyTimeSeriesPayload,
    ) -> LegacyTimeSeriesResponse:
        payload = await self._request(
            "POST",
            f"/connection-points/{connection_point_ean_code}/forecast",
            json=body.model_dump(by_alias=True, exclude_none=True),
            expected_status={200},
            required_scopes={WRITE_CONNECTION_POINT_SCOPE},
        )
        return LegacyTimeSeriesResponse.model_validate(payload)

    async def create_farm_cleared_volumes(
        self,
        body: MarketFarmTransactionsCreate,
    ) -> TransactionsCreateResponse:
        payload = await self._request(
            "POST",
            "/transactions/farm-cleared-volumes",
            json=body.model_dump(by_alias=True, exclude_none=True),
            expected_status={200},
            required_scopes={WRITE_TRANSACTIONS_SCOPE},
        )
        return TransactionsCreateResponse.model_validate(payload)

    async def get_farm_cleared_volumes(
        self,
        *,
        date_application_start_gte: datetime.datetime,
        date_application_end_lte: datetime.datetime,
        farm_ids_in: list[int] | None = None,
        market_product_time_step_in: list[ProductTimeStepApi] | None = None,
        transaction_types_in: list[AllowedTransactionType] | None = None,
        market_types_in: list[AllowedMarket] | None = None,
    ) -> FarmClearedVolumesRetrieveResponse:
        params: dict[str, Any] = {
            "dateApplicationStartGte": date_application_start_gte.isoformat(),
            "dateApplicationEndLte": date_application_end_lte.isoformat(),
            "farmIdsIn": farm_ids_in,
            "marketProductTimeStepIn": [item.value for item in market_product_time_step_in]
            if market_product_time_step_in
            else None,
            "transactionTypesIn": [item.value for item in transaction_types_in] if transaction_types_in else None,
            "marketTypesIn": [item.value for item in market_types_in] if market_types_in else None,
        }
        payload = await self._request(
            "GET",
            "/transactions/farm-cleared-volumes",
            params=params,
            required_scopes={READ_TRANSACTIONS_SCOPE},
        )
        return FarmClearedVolumesRetrieveResponse.model_validate(payload)

    async def create_metering_records(self, body: MeteringsRecordsCreate) -> MeteringRecordsCreateResponse:
        payload = await self._request(
            "POST",
            "/metering-records",
            json=body.model_dump(by_alias=True, exclude_none=True),
            expected_status={201},
            required_scopes={WRITE_METERING_SCOPE},
        )
        return MeteringRecordsCreateResponse.model_validate(payload)

    async def create_meterings_legacy(self, body: MeteringsCreateLegacy) -> MeteringRecordsCreateResponse:
        payload = await self._request(
            "POST",
            "/meterings",
            json=body.model_dump(by_alias=True, exclude_none=True),
            expected_status={201},
            required_scopes={WRITE_METERING_SCOPE},
        )
        return MeteringRecordsCreateResponse.model_validate(payload)

    async def create_weather_measurements(
        self,
        body: WeatherMeasurementsCreate,
    ) -> WeatherMeasurementsCreateResponse:
        payload = await self._request(
            "POST",
            "/weather-measurements",
            json=body.model_dump(by_alias=True, exclude_none=True),
            expected_status={201},
            required_scopes={WRITE_WEATHER_MEASUREMENT_SCOPE},
        )
        return WeatherMeasurementsCreateResponse.model_validate(payload)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | list[dict[str, Any]] | None = None,
        expected_status: set[int] | None = None,
        required_scopes: set[str] | None = None,
    ) -> Any:
        expected_status = expected_status or {200}
        token = await self._resolve_access_token(required_scopes=required_scopes or set())
        sanitized_params = {key: value for key, value in (params or {}).items() if value is not None}
        response = await self._http.request(
            method=method,
            url=f"{self._base_url}{path}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            params=sanitized_params,
            json=json,
        )
        if response.status_code not in expected_status:
            self._raise_for_status(response)
        if response.status_code == 204:
            return None
        return response.json()

    async def _resolve_access_token(self, *, required_scopes: set[str]) -> str:
        if self._cached_token and not self._cached_token.is_expired():
            self._ensure_scope_coverage(self._cached_token.scopes, required_scopes)
            return self._cached_token.access_token

        if self._auth.access_token:
            self._cached_token = _BearerToken(
                access_token=self._auth.access_token,
                scopes=set(self._auth.allowed_scopes),
            )
            self._ensure_scope_coverage(self._cached_token.scopes, required_scopes)
            return self._cached_token.access_token

        if not self._auth.client_id or not self._auth.client_secret:
            raise AeolusAuthError(
                "Missing Aeolus auth credentials: provide either access_token or client_id/client_secret.",
                status_code=401,
            )

        token = await self._fetch_client_credentials_token()
        self._cached_token = token
        self._ensure_scope_coverage(token.scopes, required_scopes)
        return token.access_token

    def _ensure_scope_coverage(self, token_scopes: set[str], required_scopes: set[str]) -> None:
        if not required_scopes:
            return
        if not token_scopes:
            return
        missing_scopes = required_scopes.difference(token_scopes)
        if missing_scopes:
            raise AeolusAuthError(
                f"Token is missing required scope(s): {', '.join(sorted(missing_scopes))}",
                status_code=403,
            )

    async def _fetch_client_credentials_token(self) -> _BearerToken:
        form: dict[str, str] = {"grant_type": "client_credentials"}
        if self._auth.token_scope:
            form["scope"] = self._auth.token_scope
        response = await self._http.post(
            self._auth.token_url,
            data=form,
            auth=(self._auth.client_id, self._auth.client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self._auth.token_timeout_seconds,
        )
        if response.status_code >= 400:
            self._raise_for_status(response)

        payload = response.json()
        access_token = payload.get("access_token")
        if not access_token:
            raise AeolusAuthError("Token endpoint response did not include access_token.", status_code=401, payload=payload)
        expires_in = payload.get("expires_in")
        expires_at: datetime.datetime | None = None
        if isinstance(expires_in, int):
            expires_at = datetime.datetime.now(tz=datetime.UTC) + datetime.timedelta(seconds=max(expires_in - 60, 0))
        token_scope = payload.get("scope")
        parsed_scopes = set(token_scope.split()) if isinstance(token_scope, str) else set()
        parsed_scopes.update(self._auth.allowed_scopes)
        return _BearerToken(access_token=access_token, expires_at=expires_at, scopes=parsed_scopes)

    def _raise_for_status(self, response: httpx.Response) -> None:
        status_code = response.status_code
        payload: Any
        message: str
        try:
            payload = response.json()
            detail = payload.get("detail")
            if isinstance(detail, str):
                message = detail
            else:
                message = f"Aeolus API error {status_code}"
        except ValueError:
            payload = response.text
            message = payload if isinstance(payload, str) and payload else f"Aeolus API error {status_code}"

        if status_code in {401}:
            raise AeolusAuthError(message, status_code=status_code, payload=payload)
        if status_code in {403}:
            raise AeolusForbiddenError(message, status_code=status_code, payload=payload)
        if status_code in {404}:
            raise AeolusNotFoundError(message, status_code=status_code, payload=payload)
        if status_code in {422}:
            raise AeolusValidationError(message, status_code=status_code, payload=payload)
        raise AeolusApiError(message, status_code=status_code, payload=payload)

