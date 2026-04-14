from __future__ import annotations

from pathlib import Path

from src.ml_models.forecasts.manager import ForecastManager as _ForecastManagerBase
from src.ml_models.forecasts.models import (
    ALLOWED_SITES,
    FORECAST_TAB_HTML,
    PARIS_TZ,
    ForecastRun,
    ForecastSchedule,
    _aggregate_scores,
    _build_feature_table,
    _choose_value_column,
    _compute_single_model,
    _discover_sites,
    _json_safe,
    _linear_regression_predict,
    _linear_regression_row_from_history,
    _load_site_timeseries,
    _load_site_timeseries_from_workflow,
    _median_profile_predict,
    _naive_day_copy_predict,
    _now_utc,
    _safe_mape,
    _score_fold,
    logger,
)
from src.ml_models.forecasts.router import build_forecast_router
from src.ml_models.forecasts.schemas import (
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


class ForecastManager(_ForecastManagerBase):
    """Backward-compatible manager that keeps module-level monkeypatch hooks."""

    def __init__(self, data_root: Path) -> None:
        super().__init__(
            data_root=data_root,
            now_utc_fn=_now_utc,
            discover_sites_fn=_discover_sites,
            load_site_timeseries_from_workflow_fn=_load_site_timeseries_from_workflow,
            compute_single_model_fn=_compute_single_model,
            json_safe_fn=_json_safe,
        )


__all__ = [
    "ALLOWED_SITES",
    "FORECAST_TAB_HTML",
    "MODEL_NAME",
    "PARIS_TZ",
    "RUN_STATUSES",
    "ForecastManager",
    "ForecastRun",
    "ForecastSchedule",
    "RunCreateRequest",
    "RunDetailResponse",
    "RunSummaryResponse",
    "ScheduleActiveUpdateRequest",
    "ScheduleCreateRequest",
    "ScheduleResponse",
    "ScheduleUpdateRequest",
    "_aggregate_scores",
    "_build_feature_table",
    "_choose_value_column",
    "_compute_single_model",
    "_discover_sites",
    "_json_safe",
    "_linear_regression_predict",
    "_linear_regression_row_from_history",
    "_load_site_timeseries",
    "_load_site_timeseries_from_workflow",
    "_median_profile_predict",
    "_naive_day_copy_predict",
    "_now_utc",
    "_safe_mape",
    "_score_fold",
    "build_forecast_router",
    "logger",
]
