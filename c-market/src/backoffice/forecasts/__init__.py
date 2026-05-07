"""Forecast backoffice package."""

from typing import TYPE_CHECKING

# from .router import build_forecast_router # commented out to keep this import minimal, to avoid circular imports
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

if TYPE_CHECKING:
    from .manager import ForecastManager


def __getattr__(name: str):
    if name == "ForecastManager":
        from .manager import ForecastManager

        return ForecastManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
]
