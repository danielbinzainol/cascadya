from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


RUN_STATUSES = Literal["queued", "running", "done", "failed"]
MODEL_NAME = Literal[
    "simple_copy",
    "median_copy",
    "linear_regression",
    # "arima",
    # "lstm",
    "all_models",
]


class RunCreateRequest(BaseModel):
    site: str = Field(min_length=1)
    model: MODEL_NAME
    n_splits: int = Field(gt=1)
    gap: int = Field(ge=0)
    test_size: int = Field(gt=0)


class ScheduleCreateRequest(BaseModel):
    site: str = Field(min_length=1)
    model: MODEL_NAME
    n_splits: int = Field(gt=1)
    gap: int = Field(ge=0)
    test_size: int = Field(gt=0)
    active: bool = True


class ScheduleUpdateRequest(BaseModel):
    site: str = Field(min_length=1)
    model: MODEL_NAME
    n_splits: int = Field(gt=1)
    gap: int = Field(ge=0)
    test_size: int = Field(gt=0)
    active: bool = True


class ScheduleResponse(BaseModel):
    schedule_id: str
    site: str
    model: MODEL_NAME
    n_splits: int
    gap: int
    test_size: int
    active: bool
    trigger_time: str
    timezone: str
    last_triggered_at: datetime | None


class ScheduleActiveUpdateRequest(BaseModel):
    active: bool


class RunSummaryResponse(BaseModel):
    run_id: str
    site: str
    model: MODEL_NAME
    trigger_source: Literal["manual", "scheduled"]
    status: RUN_STATUSES
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    queue_position: int


class RunDetailResponse(RunSummaryResponse):
    n_splits: int
    gap: int
    test_size: int
    ranking: list[dict[str, str | float]] | None
    metrics: dict[str, float | None] | None
    scoring_details: list[dict[str, object]] | None
    in_sample_chart: list[dict[str, str | float | None]] | None
    out_of_sample_chart: list[dict[str, str | float | None]] | None
    residual_chart: list[dict[str, str | float | None]] | None
    logs: str | None
    error: str | None
