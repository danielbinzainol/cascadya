from __future__ import annotations

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class RteBalancingEnergyBaseModel(BaseModel):
    model_config = ConfigDict(extra="allow", validate_by_name=True, validate_by_alias=True)


class ImbalanceDataValue(RteBalancingEnergyBaseModel):
    start_date: AwareDatetime
    end_date: AwareDatetime
    imbalance: int | None = None
    system_trend: str | None = None
    positive_imbalance_settlement_price: float | None = None
    negative_imbalance_settlement_price: float | None = None
    missing_data_list: str | None = None
    updated_date: AwareDatetime | None = None


class ImbalanceDataSeries(RteBalancingEnergyBaseModel):
    start_date: AwareDatetime
    end_date: AwareDatetime
    resolution: str | None = None
    values: list[ImbalanceDataValue] = Field(default_factory=list)


class ImbalanceDataResponse(RteBalancingEnergyBaseModel):
    imbalance_data: list[ImbalanceDataSeries]
