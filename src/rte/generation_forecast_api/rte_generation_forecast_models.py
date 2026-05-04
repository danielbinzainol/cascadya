from __future__ import annotations

import re

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class RteGenerationForecastBaseModel(BaseModel):
    model_config = ConfigDict(
        extra="allow", validate_by_name=True, validate_by_alias=True
    )

    @field_validator(
        "start_date",
        "end_date",
        "updated_date",
        mode="before",
        check_fields=False,
    )
    @classmethod
    def _normalize_rte_datetime_seconds(cls, value):  # noqa: ANN001
        if not isinstance(value, str):
            return value
        match = re.search(
            r"T\d{2}:\d{2}:(\d{2})(?:\.\d+)?(?:Z|[+\-]\d{2}:\d{2})$", value
        )
        if not match:
            return value
        seconds = int(match.group(1))
        if seconds <= 59:
            return value
        return value.replace(f":{seconds:02d}", ":59", 1)


class GenerationForecastPoint(RteGenerationForecastBaseModel):
    start_date: AwareDatetime | None = None
    end_date: AwareDatetime | None = None
    updated_date: AwareDatetime | None = None
    value: float | int | None = None


class GenerationForecastSeries(RteGenerationForecastBaseModel):
    production_type: str | None = None
    type: str | None = None
    start_date: AwareDatetime | None = None
    end_date: AwareDatetime | None = None
    values: list[GenerationForecastPoint] = Field(default_factory=list)


class GenerationForecastResponse(RteGenerationForecastBaseModel):
    forecasts: list[GenerationForecastSeries]

    @model_validator(mode="before")
    @classmethod
    def _normalize_root_payload(cls, data):  # noqa: ANN001
        if not isinstance(data, dict):
            return data

        if "forecasts" in data:
            return data
        if "generation_forecasts" in data:
            return {"forecasts": data["generation_forecasts"]}
        if "generationForecasts" in data:
            return {"forecasts": data["generationForecasts"]}

        return data


class TotalForecastSeries(RteGenerationForecastBaseModel):
    type: str | None = None
    start_date: AwareDatetime | None = None
    end_date: AwareDatetime | None = None
    values: list[GenerationForecastPoint] = Field(default_factory=list)


class TotalForecastResponse(RteGenerationForecastBaseModel):
    total_forecast: list[TotalForecastSeries]

    @model_validator(mode="before")
    @classmethod
    def _normalize_root_payload(cls, data):  # noqa: ANN001
        if not isinstance(data, dict):
            return data

        if "total_forecast" in data:
            return data
        if "totalForecast" in data:
            return {"total_forecast": data["totalForecast"]}

        return data
