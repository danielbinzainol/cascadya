from fastapi import APIRouter, FastAPI
from pydantic import BaseModel, Field, SecretStr

from src.aeolus_client import AeolusAuthConfig, AeolusClient
from src.aeolus_models import (
    AllowedMarket,
    AllowedTransactionType,
    PositionType,
    ProductTimeStepApi,
)
from src.ml_models.services import aeolus_publish_service

router = APIRouter(prefix="/aeolus", tags=["aeolus"])

DEFAULT_AEOLUS_BASE_URL = aeolus_publish_service.DEFAULT_AEOLUS_BASE_URL
DEFAULT_AEOLUS_TOKEN_URL = aeolus_publish_service.DEFAULT_AEOLUS_TOKEN_URL
DEFAULT_AEOLUS_WRITE_TRANSACTIONS_SCOPE = (
    aeolus_publish_service.DEFAULT_AEOLUS_WRITE_TRANSACTIONS_SCOPE
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


def _resolve_auth_config(auth_input: PublishAeolusAuthInput | None) -> AeolusAuthConfig:
    return aeolus_publish_service.resolve_auth_config(auth_input)


def _resolve_publish_csv_paths(project: str, file_ids: list[str] | None):
    return aeolus_publish_service.resolve_publish_csv_paths(project, file_ids)


@router.post(
    "/publish-market-orders/{project}",
    response_model=PublishMarketOrdersResponse,
)
async def publish_market_orders(project: str, payload: PublishMarketOrdersRequest):
    result = await aeolus_publish_service.publish_market_orders_workflow(
        project=project,
        payload=payload,
        csv_paths_resolver=_resolve_publish_csv_paths,
        auth_config_resolver=_resolve_auth_config,
        aeolus_client_cls=AeolusClient,
    )

    return PublishMarketOrdersResponse(
        source_files=result.source_files,
        transactions_submitted=result.transactions_submitted,
        transaction_ids=result.transaction_ids,
        aeolus_base_url=result.aeolus_base_url,
    )


app = FastAPI()
app.include_router(router)
