from __future__ import annotations

import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AeolusBaseModel(BaseModel):
    model_config = ConfigDict(extra="allow", validate_by_name=True, validate_by_alias=True)

class ForecastVersion(str, Enum):
    LATEST = "latest"
    DAYAHEAD = "dayahead"


class ProductTimeStep(str, Enum):
    HOUR = "hour"
    QUARTER_OF_AN_HOUR = "quarter of an hour"


class ProductTimeStepApi(str, Enum):
    HOUR = "hour"
    QUARTER_OF_AN_HOUR = "quarter of an hour"


class AllowedMarket(str, Enum):
    DAY_AHEAD = "Day Ahead"
    INTRADAY_CONTINUOUS = "Intraday Continuous"


class AllowedTransactionType(str, Enum):
    MARKET = "Market"


class PositionType(str, Enum):
    SALE = "Sale"
    PURCHASE = "Purchase"


class TransactionType(str, Enum):
    DAYAHEAD = "dayahead"
    INTRADAY = "intraday"
    OTC = "otc"
    ARENH = "arenh"
    FUTURE = "future"


class AssetModel(AeolusBaseModel):
    id: int
    name: str | None = None


class AssetTimeSeriesPoint(AeolusBaseModel):
    datetime: datetime.datetime
    power_kw: int | float = Field(alias="powerkW")
    time_step_minutes: int = Field(alias="timeStepMinutes")


class ForecastAssetTimeSeriesPoint(AssetTimeSeriesPoint):
    date_creation: datetime.datetime = Field(alias="dateCreation")


class AssetPointsWithCreatedDate(AeolusBaseModel):
    asset_id: int = Field(alias="assetId")
    start: datetime.datetime
    end: datetime.datetime
    points: list[AssetTimeSeriesPoint]
    created_after: datetime.datetime | None = Field(alias="createdAfter")
    created_before:datetime.datetime | None = Field(alias="createdBefore")


class AssetTimeSeriesPayload(AeolusBaseModel):
    points: list[AssetTimeSeriesPoint]


class AssetTimeSeriesResponse(AeolusBaseModel):
    start: datetime.datetime
    end: datetime.datetime
    points: list[AssetTimeSeriesPoint]


class ForecastAssetPoints(AeolusBaseModel):
    asset_id: int = Field(alias="assetId")
    start: datetime.datetime
    end: datetime.datetime
    points: list[ForecastAssetTimeSeriesPoint]


class Maintenance(AeolusBaseModel):
    id: int
    start_date: datetime.datetime = Field(alias="startDate")
    end_date: datetime.datetime = Field(alias="endDate")
    maintenance_nature_id: int = Field(alias="maintenanceNatureId")
    producing_unit_id: int = Field(alias="producingUnitId")
    prod_max_in_p: int | None = Field(default=None, alias="prodMaxInP")
    prod_max_in_mw: float | None = Field(default=None, alias="prodMaxInMW")
    maintenance_strategy_id: int | None = Field(default=None, alias="maintenanceStrategyId")
    maintenance_group_id: int | None = Field(default=None, alias="maintenanceGroupId")
    description: str | None = None


class MaintenancePayload(AeolusBaseModel):
    start_date: datetime.datetime = Field(alias="startDate")
    end_date: datetime.datetime = Field(alias="endDate")
    maintenance_nature_id: int = Field(alias="maintenanceNatureId")
    producing_unit_ids: list[int] = Field(alias="producingUnitIds")
    prod_max_in_p: int | None = Field(default=None, alias="prodMaxInP")
    prod_max_in_mw: float | None = Field(default=None, alias="prodMaxInMW")
    maintenance_strategy_id: int | None = Field(default=None, alias="maintenanceStrategyId")
    description: str | None = None


class MaintenanceResponse(AeolusBaseModel):
    start_date: datetime.datetime = Field(alias="startDate")
    end_date: datetime.datetime = Field(alias="endDate")
    maintenance_nature_id: int = Field(alias="maintenanceNatureId")
    producing_unit_ids: list[int] = Field(alias="producingUnitIds")
    prod_max_in_p: int | None = Field(default=None, alias="prodMaxInP")
    prod_max_in_mw: float | None = Field(default=None, alias="prodMaxInMW")
    maintenance_strategy_id: int | None = Field(default=None, alias="maintenanceStrategyId")
    maintenance_group_id: int | None = Field(default=None, alias="maintenanceGroupId")
    description: str | None = None


class WeatherMeteringPoint(AeolusBaseModel):
    datetime: datetime.datetime
    time_step_minutes: int = Field(alias="timeStepMinutes")
    irradiance_wm2: float | None = Field(default=None, alias="irradianceWm2")
    temperature_c: float | None = Field(default=None, alias="temperatureC")
    wind_speed_ms: float | None = Field(default=None, alias="windSpeedMs")
    wind_direction_deg: float | None = Field(default=None, alias="windDirectionDeg")


class WeatherMeteringPoints(AeolusBaseModel):
    asset_id: int = Field(alias="assetId")
    start: datetime.datetime
    end: datetime.datetime
    points: list[WeatherMeteringPoint]


class PortfolioModel(AeolusBaseModel):
    id: int
    name: str


class PortfoliosPayload(AeolusBaseModel):
    portfolios: list[PortfolioModel]


class SpotPrice(AeolusBaseModel):
    datetime: datetime.datetime
    price: str
    time_step_minutes: int = Field(alias="timeStepMinutes")
    unit: str | None = None


class SpotPriceResponse(AeolusBaseModel):
    country: str
    start: datetime.datetime
    end: datetime.datetime
    points: list[SpotPrice]


class ImbalancePrice(AeolusBaseModel):
    datetime: datetime.datetime
    time_step_minutes: int = Field(alias="timeStepMinutes")
    price_up: str | None = Field(default=None, alias="priceUp")
    price_down: str | None = Field(default=None, alias="priceDown")


class ImbalancePriceResponse(AeolusBaseModel):
    country: str
    start: datetime.datetime
    end: datetime.datetime
    points: list[ImbalancePrice]


class Transaction(AeolusBaseModel):
    start: datetime.datetime
    end: datetime.datetime
    quantity: str
    unit: str
    transaction_type: str = Field(alias="transactionType")
    position_type: str = Field(alias="positionType")
    price_in_euro_by_mwh: str | None = Field(alias="priceInEuroByMwh")


class PortfolioTransactionsResponse(AeolusBaseModel):
    start: datetime.datetime
    end: datetime.datetime
    points: list[Transaction]
    portfolio_id: int = Field(alias="portfolioId")


class LegacyTimeSeriesPoint(AeolusBaseModel):
    datetime: datetime.datetime
    value: int | float | str
    time_step_minutes: int = Field(alias="timeStepMinutes")


class LegacyTimeSeriesPayload(AeolusBaseModel):
    points: list[LegacyTimeSeriesPoint]


class LegacyTimeSeriesResponse(AeolusBaseModel):
    connection_point_ean_code: str | None = Field(default=None, alias="connectionPointEanCode")
    start: datetime.datetime
    end: datetime.datetime
    points: list[LegacyTimeSeriesPoint]


class TransactionCreate(AeolusBaseModel):
    farm_id: int = Field(alias="farmId")
    date_application_start: datetime.datetime = Field(alias="dateApplicationStart")
    market_product_time_step: ProductTimeStepApi = Field(alias="marketProductTimeStep")
    quantity_in_kw: int = Field(alias="quantityInkW")
    price_in_euro_by_mwh: float | str = Field(alias="priceInEuroByMwh")
    position_type: PositionType = Field(alias="positionType")
    market: AllowedMarket
    transaction_type: AllowedTransactionType = Field(alias="transactionType")


class MarketFarmTransactionsCreate(AeolusBaseModel):
    transactions: list[TransactionCreate]


class TransactionsCreateResponse(AeolusBaseModel):
    transaction_ids: list[int] = Field(alias="transactionIds")


class FarmClearedVolumeItem(AeolusBaseModel):
    cleared_volume_id: int = Field(alias="clearedVolumeId")
    farm_id: int = Field(alias="farmId")
    portfolio_id: int = Field(alias="portfolioId")
    market: str
    transaction_type: str = Field(alias="transactionType")
    product_time_step: str = Field(alias="productTimeStep")
    date_application_start: datetime.datetime = Field(alias="dateApplicationStart")
    date_application_end: datetime.datetime = Field(alias="dateApplicationEnd")
    quantity_in_kw: str = Field(alias="quantityInkW")
    price_in_euro_by_mwh: float | str = Field(alias="priceInEuroByMwh")
    notional: float | str | None = None


class FarmClearedVolumesRetrieveResponse(AeolusBaseModel):
    farm_cleared_volumes: list[FarmClearedVolumeItem] = Field(alias="farmClearedVolumes")


class MeteringRecordCreate(AeolusBaseModel):
    producing_unit_id: int = Field(alias="producingUnitId")
    date_application: datetime.datetime = Field(alias="dateApplication")
    metered_power_kw: float | str | None = Field(alias="meteredPowerkW")


class MeteringsRecordsCreate(AeolusBaseModel):
    metering_records: list[MeteringRecordCreate] = Field(alias="meteringRecords")


class MeteringsCreateLegacy(AeolusBaseModel):
    meterings: list[MeteringRecordCreate]


class MeteringRecordsCreateResponse(AeolusBaseModel):
    message: str
    count: int


class WeatherMeasurementCreate(AeolusBaseModel):
    producing_unit_id: int = Field(alias="producingUnitId")
    date_application: datetime.datetime = Field(alias="dateApplication")
    wind_speed_in_m_per_s: float | None = Field(alias="windSpeedInMPerS")
    wind_direction_in_degrees: float | None = Field(alias="windDirectionInDegrees")
    temperature_in_celsius: float | None = Field(alias="temperatureInCelsius")
    pressure_in_pa: float | None = Field(alias="pressureInPa")
    relative_humidity_in_percent: float | None = Field(alias="relativeHumidityInPercent")
    global_horizontal_irradiance_in_w_per_m2: float | None = Field(alias="globalHorizontalIrradianceInWPerM2")
    diffuse_horizontal_irradiance_in_w_per_m2: float | None = Field(alias="diffuseHorizontalIrradianceInWPerM2")
    direct_normal_irradiance_in_w_per_m2: float | None = Field(alias="directNormalIrradianceInWPerM2")


class WeatherMeasurementsCreate(AeolusBaseModel):
    weather_measurements: list[WeatherMeasurementCreate] = Field(alias="weatherMeasurements")


class WeatherMeasurementsCreateResponse(AeolusBaseModel):
    message: str
    count: int

