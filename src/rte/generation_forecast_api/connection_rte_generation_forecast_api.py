from __future__ import annotations

import datetime
import os

from fastapi import FastAPI, HTTPException, Query

from src.rte.rte_client import (
    DEFAULT_RTE_GENERATION_FORECAST_BASE_URL,
    RteApiError,
    RteAuthConfig,
    RteAuthError,
    RteGenerationForecastClient,
)
from src.rte.rte_auth import resolve_rte_auth_env
from src.rte.generation_forecast_api.rte_generation_forecast_models import (
    GenerationForecastResponse,
    TotalForecastResponse,
)

app = FastAPI()


@app.get("/rte/generation-forecast/forecasts", response_model=GenerationForecastResponse)
async def get_rte_generation_forecasts(
    production_types: list[str] | None = Query(default=None, alias="production_type"),
    type_values: list[str] | None = Query(default=None, alias="type"),
    start_date: datetime.datetime | None = None,
    end_date: datetime.datetime | None = None,
) -> GenerationForecastResponse:
    resolved_auth = resolve_rte_auth_env()
    auth_config = RteAuthConfig(
        access_token=resolved_auth.access_token,
        client_id=resolved_auth.client_id,
        client_secret=resolved_auth.client_secret,
        basic_authorization_b64=resolved_auth.basic_authorization_b64,
        token_url=resolved_auth.token_url,
    )
    base_url = os.getenv("RTE_GENERATION_FORECAST_BASE_URL", DEFAULT_RTE_GENERATION_FORECAST_BASE_URL)

    try:
        async with RteGenerationForecastClient(base_url=base_url, auth=auth_config) as client:
            return await client.get_forecasts(
                production_types=production_types,
                forecast_types=type_values,
                start_date=start_date,
                end_date=end_date,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RteAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except RteApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.get("/rte/generation-forecast/total-forecast", response_model=TotalForecastResponse)
async def get_rte_generation_total_forecast(
    type_values: list[str] | None = Query(default=None, alias="type"),
    start_date: datetime.datetime | None = None,
    end_date: datetime.datetime | None = None,
) -> TotalForecastResponse:
    resolved_auth = resolve_rte_auth_env()
    auth_config = RteAuthConfig(
        access_token=resolved_auth.access_token,
        client_id=resolved_auth.client_id,
        client_secret=resolved_auth.client_secret,
        basic_authorization_b64=resolved_auth.basic_authorization_b64,
        token_url=resolved_auth.token_url,
    )
    base_url = os.getenv("RTE_GENERATION_FORECAST_BASE_URL", DEFAULT_RTE_GENERATION_FORECAST_BASE_URL)

    try:
        async with RteGenerationForecastClient(base_url=base_url, auth=auth_config) as client:
            return await client.get_total_forecast(
                forecast_types=type_values,
                start_date=start_date,
                end_date=end_date,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RteAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except RteApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
