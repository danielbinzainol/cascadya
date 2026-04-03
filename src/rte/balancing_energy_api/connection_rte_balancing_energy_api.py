from __future__ import annotations

import datetime
import os

from fastapi import FastAPI, HTTPException

from src.rte.rte_client import (
    DEFAULT_RTE_BALANCING_ENERGY_BASE_URL,
    RteApiError,
    RteAuthConfig,
    RteAuthError,
    RteBalancingEnergyClient,
)
from src.rte.balancing_energy_api.rte_balancing_energy_models import (
    ImbalanceDataResponse,
)
from src.rte.rte_auth import resolve_rte_auth_env

app = FastAPI()


@app.get("/rte/balancing-energy/imbalance-data", response_model=ImbalanceDataResponse)
async def get_rte_balancing_energy_imbalance_data(
    start_date: datetime.datetime | None = None,
    end_date: datetime.datetime | None = None,
) -> ImbalanceDataResponse:
    resolved_auth = resolve_rte_auth_env()
    auth_config = RteAuthConfig(
        access_token=resolved_auth.access_token,
        client_id=resolved_auth.client_id,
        client_secret=resolved_auth.client_secret,
        basic_authorization_b64=resolved_auth.basic_authorization_b64,
        token_url=resolved_auth.token_url,
    )
    base_url = os.getenv(
        "RTE_BALANCING_ENERGY_BASE_URL", DEFAULT_RTE_BALANCING_ENERGY_BASE_URL
    )

    try:
        async with RteBalancingEnergyClient(
            base_url=base_url, auth=auth_config
        ) as client:
            return await client.get_imbalance_data(
                start_date=start_date, end_date=end_date
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RteAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except RteApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
