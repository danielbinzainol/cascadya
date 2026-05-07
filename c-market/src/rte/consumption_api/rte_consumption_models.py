from __future__ import annotations

from enum import Enum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class RteConsumptionBaseModel(BaseModel):
    model_config = ConfigDict(
        extra="allow", validate_by_name=True, validate_by_alias=True
    )


class ShortTermQueryType(str, Enum):
    REALISED = "REALISED"
    ID = "ID"
    DAY_AHEAD = "D-1"
    DAY_AHEAD_PLUS_1 = "D-2"


class ShortTermResponseType(str, Enum):
    ACTUAL = "ACTUAL"
    REALISED = "REALISED"
    ID = "ID"
    DAY_AHEAD = "D-1"
    DAY_AHEAD_PLUS_1 = "D-2"


class RteApiErrorDetails(RteConsumptionBaseModel):
    transaction_id: str | None = None


class RteApiErrorPayload(RteConsumptionBaseModel):
    error: str | None = None
    error_description: str | None = None
    error_uri: str | None = None
    error_details: RteApiErrorDetails | None = None


class ShortTermPoint(RteConsumptionBaseModel):
    start_date: AwareDatetime
    end_date: AwareDatetime
    updated_date: AwareDatetime
    value: int


class ShortTermSeries(RteConsumptionBaseModel):
    type: ShortTermResponseType
    start_date: AwareDatetime
    end_date: AwareDatetime
    values: list[ShortTermPoint] = Field(default_factory=list)


class ShortTermResponse(RteConsumptionBaseModel):
    short_term: list[ShortTermSeries]
