from __future__ import annotations

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class RteGenerationForecastBaseModel(BaseModel):
    model_config = ConfigDict(extra="allow", validate_by_name=True, validate_by_alias=True)


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
