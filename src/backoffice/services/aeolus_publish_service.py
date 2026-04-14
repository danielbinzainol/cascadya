import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from fastapi import HTTPException

from src.aeolus_client import (
    AeolusApiError,
    AeolusAuthConfig,
    AeolusAuthError,
    AeolusClient,
)
from src.aeolus_market_bridge import market_orders_paths_to_payload
from src.market_orders import complex_market_orders_data_workflow
from src.market_orders_paths import resolve_market_orders_csv_path

DEFAULT_AEOLUS_BASE_URL = "https://e6.aeolus.main.e6-group.com/api/v2"
DEFAULT_AEOLUS_TOKEN_URL = (
    "https://eole-api-gateway-prod.auth.eu-west-1.amazoncognito.com/oauth2/token"
)
DEFAULT_AEOLUS_WRITE_TRANSACTIONS_SCOPE = (
    "https://aeolus.main.e6-group.com/write:transactions"
)


@dataclass
class PublishMarketOrdersResult:
    source_files: list[str]
    transactions_submitted: int
    transaction_ids: list[int]
    aeolus_base_url: str


def split_scope_values(raw_scopes: str | None) -> set[str]:
    if not raw_scopes:
        return set()
    return {scope for scope in raw_scopes.replace(",", " ").split() if scope}


def resolve_auth_config(auth_input) -> AeolusAuthConfig:
    env_access_token = os.getenv("AEOLUS_ACCESS_TOKEN")
    env_client_id = os.getenv("AEOLUS_CLIENT_ID")
    env_client_secret = os.getenv("AEOLUS_CLIENT_SECRET")
    env_allowed_scopes = split_scope_values(os.getenv("AEOLUS_ALLOWED_SCOPES"))
    env_token_scope = os.getenv(
        "AEOLUS_TOKEN_SCOPE", DEFAULT_AEOLUS_WRITE_TRANSACTIONS_SCOPE
    )
    env_token_url = os.getenv("AEOLUS_TOKEN_URL", DEFAULT_AEOLUS_TOKEN_URL)

    token_value = (
        auth_input.access_token.get_secret_value()
        if auth_input and auth_input.access_token
        else env_access_token
    )
    client_id = (
        auth_input.client_id if auth_input and auth_input.client_id else env_client_id
    )
    client_secret = (
        auth_input.client_secret.get_secret_value()
        if auth_input and auth_input.client_secret
        else env_client_secret
    )
    token_url = auth_input.token_url if auth_input else env_token_url
    token_scope = auth_input.token_scope if auth_input else env_token_scope

    allowed_scopes = set(auth_input.allowed_scopes) if auth_input else set()
    allowed_scopes.update(env_allowed_scopes)

    if not token_value and not (client_id and client_secret):
        raise HTTPException(
            status_code=400,
            detail=(
                "Missing Aeolus credentials. Provide auth.access_token, "
                "or auth.client_id/auth.client_secret, or set AEOLUS_ACCESS_TOKEN "
                "or AEOLUS_CLIENT_ID/AEOLUS_CLIENT_SECRET."
            ),
        )

    return AeolusAuthConfig(
        access_token=token_value,
        allowed_scopes=allowed_scopes,
        token_url=token_url,
        client_id=client_id,
        client_secret=client_secret,
        token_scope=token_scope,
    )


def resolve_publish_csv_paths(project: str, file_ids: list[str] | None) -> list[Path]:
    if not file_ids:
        return complex_market_orders_data_workflow(project)
    return [resolve_market_orders_csv_path(project, file_id) for file_id in file_ids]


async def publish_market_orders_workflow(
    *,
    project: str,
    payload,
    csv_paths_resolver: Callable[
        [str, list[str] | None], list[Path]
    ] = resolve_publish_csv_paths,
    auth_config_resolver: Callable[
        [object | None], AeolusAuthConfig
    ] = resolve_auth_config,
    aeolus_client_cls=AeolusClient,
) -> PublishMarketOrdersResult:
    csv_paths = csv_paths_resolver(project, payload.file_ids)
    transactions_payload = market_orders_paths_to_payload(
        csv_paths,
        farm_id=payload.farm_id,
        market=payload.market,
        transaction_type=payload.transaction_type,
        position_type=payload.position_type,
        default_product_time_step=payload.default_product_time_step,
        drop_zero_quantities=payload.drop_zero_quantities,
    )
    if not transactions_payload.transactions:
        raise HTTPException(
            status_code=400,
            detail="No publishable market orders found (all quantities are zero).",
        )

    auth_config = auth_config_resolver(payload.auth)

    try:
        async with aeolus_client_cls(
            base_url=payload.aeolus_base_url, auth=auth_config
        ) as client:
            create_response = await client.create_farm_cleared_volumes(
                transactions_payload
            )
    except AeolusAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except AeolusApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return PublishMarketOrdersResult(
        source_files=[str(path) for path in csv_paths],
        transactions_submitted=len(transactions_payload.transactions),
        transaction_ids=create_response.transaction_ids,
        aeolus_base_url=payload.aeolus_base_url,
    )
