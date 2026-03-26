from __future__ import annotations

import datetime
import os

from fastapi import FastAPI, HTTPException, Query

from src.rte.rte_client import (
    DEFAULT_RTE_CONSUMPTION_BASE_URL,
    RteApiError,
    RteAuthConfig,
    RteAuthError,
    RteConsumptionClient,
)
from src.rte.rte_auth import resolve_rte_auth_env
from src.rte.consumption_api.rte_consumption_models import ShortTermQueryType, ShortTermResponse

app = FastAPI()


@app.get("/rte/consumption/short-term", response_model=ShortTermResponse)
async def get_rte_consumption_short_term(
    type_values: list[ShortTermQueryType] | None = Query(default=None, alias="type"),
    start_date: datetime.datetime | None = None,
    end_date: datetime.datetime | None = None,
) -> ShortTermResponse:
    resolved_auth = resolve_rte_auth_env()
    auth_config = RteAuthConfig(
        access_token=resolved_auth.access_token,
        client_id=resolved_auth.client_id,
        client_secret=resolved_auth.client_secret,
        basic_authorization_b64=resolved_auth.basic_authorization_b64,
        token_url=resolved_auth.token_url,
    )
    base_url = os.getenv("RTE_CONSUMPTION_BASE_URL", DEFAULT_RTE_CONSUMPTION_BASE_URL)

    try:
        async with RteConsumptionClient(base_url=base_url, auth=auth_config) as client:
            return await client.get_short_term(
                types=type_values,
                start_date=start_date,
                end_date=end_date,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RteAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except RteApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
