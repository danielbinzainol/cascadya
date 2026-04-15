"""Forecast backoffice package."""

from .manager import ForecastManager
from .router import build_forecast_router
from .schemas import (
    MODEL_NAME,
    RUN_STATUSES,
    RunCreateRequest,
    RunDetailResponse,
    RunSummaryResponse,
    ScheduleActiveUpdateRequest,
    ScheduleCreateRequest,
    ScheduleResponse,
    ScheduleUpdateRequest,
)

__all__ = [
    "ForecastManager",
    "MODEL_NAME",
    "RUN_STATUSES",
    "RunCreateRequest",
    "RunDetailResponse",
    "RunSummaryResponse",
    "ScheduleActiveUpdateRequest",
    "ScheduleCreateRequest",
    "ScheduleResponse",
    "ScheduleUpdateRequest",
    "build_forecast_router",
]
