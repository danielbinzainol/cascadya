import os
from pathlib import Path
from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, Field, SecretStr

from src.aeolus_client import (
    AeolusApiError,
    AeolusAuthConfig,
    AeolusAuthError,
    AeolusClient,
)
from src.aeolus_market_bridge import market_orders_paths_to_payload
from src.aeolus_models import (
    AllowedMarket,
    AllowedTransactionType,
    PositionType,
    ProductTimeStepApi,
)

from src.market_orders import complex_market_orders_data_workflow
from src.market_orders_paths import resolve_market_orders_csv_path

router = APIRouter(prefix="/aeolus", tags=["aeolus"])

DEFAULT_AEOLUS_BASE_URL = "https://e6.aeolus.main.e6-group.com/api/v2"
DEFAULT_AEOLUS_TOKEN_URL = (
    "https://eole-api-gateway-prod.auth.eu-west-1.amazoncognito.com/oauth2/token"
)
DEFAULT_AEOLUS_WRITE_TRANSACTIONS_SCOPE = (
    "https://aeolus.main.e6-group.com/write:transactions"
)


class PublishAeolusAuthInput(BaseModel):
    access_token: SecretStr | None = None
    allowed_scopes: list[str] = Field(default_factory=list)
    token_url: str = DEFAULT_AEOLUS_TOKEN_URL
    client_id: str | None = None
    client_secret: SecretStr | None = None
    token_scope: str = DEFAULT_AEOLUS_WRITE_TRANSACTIONS_SCOPE


class PublishMarketOrdersRequest(BaseModel):
    farm_id: int = Field(gt=0)
    file_ids: list[str] | None = None
    aeolus_base_url: str = DEFAULT_AEOLUS_BASE_URL
    auth: PublishAeolusAuthInput | None = None
    market: AllowedMarket = AllowedMarket.DAY_AHEAD
    transaction_type: AllowedTransactionType = AllowedTransactionType.MARKET
    position_type: PositionType = PositionType.PURCHASE
    default_product_time_step: ProductTimeStepApi = (
        ProductTimeStepApi.QUARTER_OF_AN_HOUR
    )
    drop_zero_quantities: bool = True


class PublishMarketOrdersResponse(BaseModel):
    source_files: list[str]
    transactions_submitted: int
    transaction_ids: list[int]
    aeolus_base_url: str


def _split_scope_values(raw_scopes: str | None) -> set[str]:
    if not raw_scopes:
        return set()
    return {scope for scope in raw_scopes.replace(",", " ").split() if scope}


def _resolve_auth_config(auth_input: PublishAeolusAuthInput | None) -> AeolusAuthConfig:
    env_access_token = os.getenv("AEOLUS_ACCESS_TOKEN")
    env_client_id = os.getenv("AEOLUS_CLIENT_ID")
    env_client_secret = os.getenv("AEOLUS_CLIENT_SECRET")
    env_allowed_scopes = _split_scope_values(os.getenv("AEOLUS_ALLOWED_SCOPES"))
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


def _resolve_publish_csv_paths(project: str, file_ids: list[str] | None) -> list[Path]:
    if not file_ids:
        return complex_market_orders_data_workflow(project)
    return [resolve_market_orders_csv_path(project, file_id) for file_id in file_ids]


@router.post(
    "/publish-market-orders/{project}",
    response_model=PublishMarketOrdersResponse,
)
async def publish_market_orders(project: str, payload: PublishMarketOrdersRequest):
    csv_paths = _resolve_publish_csv_paths(project, payload.file_ids)
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

    auth_config = _resolve_auth_config(payload.auth)

    try:
        async with AeolusClient(
            base_url=payload.aeolus_base_url, auth=auth_config
        ) as client:
            create_response = await client.create_farm_cleared_volumes(
                transactions_payload
            )
    except AeolusAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except AeolusApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return PublishMarketOrdersResponse(
        source_files=[str(path) for path in csv_paths],
        transactions_submitted=len(transactions_payload.transactions),
        transaction_ids=create_response.transaction_ids,
        aeolus_base_url=payload.aeolus_base_url,
    )


app = FastAPI()
app.include_router(router)
