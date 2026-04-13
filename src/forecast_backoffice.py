from __future__ import annotations

import asyncio
import csv
import io
import logging
import traceback
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sklearn.linear_model import LinearRegression
from sklearn.metrics import (
    mean_absolute_error,
    r2_score,
    root_mean_squared_error,
)
from sklearn.model_selection import TimeSeriesSplit

from src.dataset import (
    add_missing_timestamps_with_previous_value,
    equivalent_constant_rate_on_15min,
)
from src.ingest import data_workflow


PARIS_TZ = ZoneInfo("Europe/Paris")
FORECAST_TAB_HTML = (
    Path(__file__).resolve().parent.parent / "static" / "forecasts" / "index.html"
)
ALLOWED_SITES: tuple[str, ...] = ("inariz",)
RUN_STATUSES = Literal["queued", "running", "done", "failed"]
MODEL_NAME = Literal[
    "simple_copy",
    "median_copy",
    "linear_regression",
    # "arima",
    # "lstm",
    "all_models",
]

logger = logging.getLogger("forecast_backoffice")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("[forecast_backoffice] %(asctime)s %(levelname)s %(message)s")
    )
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


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


@dataclass
class ForecastRun:
    run_id: str
    site: str
    model: MODEL_NAME
    n_splits: int
    gap: int
    test_size: int
    trigger_source: Literal["manual", "scheduled"]
    status: RUN_STATUSES
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    queue_position: int = 0
    ranking: list[dict[str, str | float]] | None = None
    metrics: dict[str, float | None] | None = None
    scoring_details: list[dict[str, object]] | None = None
    in_sample_chart: list[dict[str, str | float | None]] | None = None
    out_of_sample_chart: list[dict[str, str | float | None]] | None = None
    residual_chart: list[dict[str, str | float | None]] | None = None
    logs: str | None = None
    error: str | None = None
    csv_buffer: str | None = None


@dataclass
class ForecastSchedule:
    schedule_id: str
    site: str
    model: MODEL_NAME
    n_splits: int
    gap: int
    test_size: int
    active: bool
    trigger_time: time
    timezone: str
    last_triggered_at: datetime | None = None


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _discover_sites(data_root: Path) -> list[str]:
    logger.info("enter _discover_sites")
    _ = data_root
    return list(ALLOWED_SITES)


def _choose_value_column(frame: pd.DataFrame) -> str:
    numeric_cols = [
        col
        for col in frame.columns
        if col != "measured_at_utc" and pd.api.types.is_numeric_dtype(frame[col])
    ]
    if not numeric_cols:
        raise ValueError("No numeric target column found in source dataframe.")
    if "Valeur" in numeric_cols:
        return "Valeur"
    return numeric_cols[0]


def _load_site_timeseries(data_root: Path, site: str) -> pd.DataFrame:
    logger.info("enter _load_site_timeseries site=%s", site)
    raw_dir = data_root / "data" / site / "raw"
    if not raw_dir.exists():
        raise ValueError(f"No raw directory found for site '{site}'.")
    candidates = sorted(
        raw_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not candidates:
        raise ValueError(f"No CSV input found for site '{site}'.")
    csv_path = candidates[0]
    frame = pd.read_csv(csv_path, sep=";", decimal=",", skiprows=4)
    if "Horodatage" not in frame.columns:
        raise ValueError(f"Unsupported format for site '{site}' file: {csv_path.name}.")
    frame["Horodatage"] = pd.to_datetime(
        frame["Horodatage"],
        errors="coerce",
        format="%Y-%m-%d %H:%M:%S.%f",
    )
    frame = frame.dropna(subset=["Horodatage"]).sort_values("Horodatage")
    frame["measured_at_utc"] = (
        frame["Horodatage"].dt.tz_localize(PARIS_TZ).dt.tz_convert("UTC")
    )
    value_col = _choose_value_column(frame)
    out = frame[["measured_at_utc", value_col]].rename(columns={value_col: "target"})
    out = out.groupby("measured_at_utc", as_index=False)["target"].mean()
    out = (
        out.set_index("measured_at_utc").resample("15min").mean().ffill().reset_index()
    )
    if len(out) < 200:
        raise ValueError("Not enough history points to run cross-validation.")
    return out


def _load_site_timeseries_from_workflow(data_root: Path, site: str) -> pd.DataFrame:
    logger.info("enter _load_site_timeseries_from_workflow site=%s", site)
    # Requested v1 ingestion path for forecasting runs:
    # build series from data_workflow and concatenate source files.
    if site != "inariz":
        return _load_site_timeseries(data_root, site)

    raw_dir = data_root / "data" / site / "raw"
    preferred_filenames = [
        "inariz_steam_prod_2026-03-09_to_2026-03-12.csv",
        "inariz_steam_prod_2026-03-13_to_2026-03-16.csv",
    ]
    existing_preferred = [
        name for name in preferred_filenames if (raw_dir / name).exists()
    ]
    filenames = existing_preferred or [p.name for p in sorted(raw_dir.glob("*.csv"))]
    if not filenames:
        return _load_site_timeseries(data_root, site)

    list_df: list[pd.DataFrame] = []
    for filename in filenames:
        df = data_workflow(site, "steam_prod", filename)
        if "Valeur" in df.columns:
            df = df.rename(columns={"Valeur": "steam_production_m3_h"})
        list_df.append(df)

    steam_prod = pd.concat(list_df, ignore_index=True)
    if "measured_at_utc" not in steam_prod.columns:
        raise ValueError("Workflow output must contain 'measured_at_utc'.")
    if "steam_production_m3_h" not in steam_prod.columns:
        raise ValueError(
            "Workflow output must contain 'steam_production_m3_h' (renamed from 'Valeur')."
        )
    steam_prod["measured_at_utc"] = pd.to_datetime(
        steam_prod["measured_at_utc"], utc=True
    )
    # Normalize timestamps on exact quarter-hours to avoid odd seconds/milliseconds on x-axis.
    steam_prod["measured_at_utc"] = steam_prod["measured_at_utc"].dt.floor("15min")

    # Use existing repo preprocessing sequence from notebook workflows.
    steam_prod = add_missing_timestamps_with_previous_value(
        steam_prod,
        timestamp_col="measured_at_utc",
        value_col="steam_production_m3_h",
        freq="15min",
    )
    steam_prod = equivalent_constant_rate_on_15min(
        steam_prod,
        timestamp_col="measured_at_utc",
        value_col="steam_production_m3_h",
        freq="15min",
    )

    if "bin_start" in steam_prod.columns:
        out = steam_prod[["bin_start", "equivalent_steam_production_m3_h"]].rename(
            columns={
                "bin_start": "measured_at_utc",
                "equivalent_steam_production_m3_h": "target",
            }
        )
    else:
        out = steam_prod[
            ["measured_at_utc", "equivalent_steam_production_m3_h"]
        ].rename(columns={"equivalent_steam_production_m3_h": "target"})
    out["measured_at_utc"] = pd.to_datetime(out["measured_at_utc"], utc=True).dt.floor(
        "15min"
    )
    out = (
        out.dropna(subset=["target"])
        .groupby("measured_at_utc", as_index=False)["target"]
        .mean()
    )
    out = out.sort_values("measured_at_utc").reset_index(drop=True)
    if len(out) < 200:
        raise ValueError("Not enough history points to run cross-validation.")
    return out


def _build_feature_table(y: pd.Series) -> pd.DataFrame:
    idx = y.index
    hour = idx.hour
    dow = idx.dayofweek
    return pd.DataFrame(
        {
            "lag_1": y.shift(1),
            "lag_4": y.shift(4),
            "lag_96": y.shift(96),
            "hour_sin": np.sin(2 * np.pi * hour / 24),
            "hour_cos": np.cos(2 * np.pi * hour / 24),
            "dow_sin": np.sin(2 * np.pi * dow / 7),
            "dow_cos": np.cos(2 * np.pi * dow / 7),
        },
        index=idx,
    )


def _safe_mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    clipped = np.clip(np.abs(y_true), 1e-6, None)
    return float(np.mean(np.abs((y_true - y_pred) / clipped)))


def _score_fold(
    y_true: np.ndarray, y_pred: np.ndarray, train_seconds: float
) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(root_mean_squared_error(y_true, y_pred)),
        "mape": _safe_mape(y_true, y_pred),
        "r2": float(r2_score(y_true, y_pred)),
        "train_time_seconds": train_seconds,
    }


def _aggregate_scores(scores: list[dict[str, float]]) -> dict[str, float]:
    keys = ["mae", "rmse", "mape", "r2", "train_time_seconds"]
    return {k: float(np.mean([s[k] for s in scores])) for k in keys}


def _json_safe(value):
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        if not np.isfinite(value):
            return None
        return value
    return value


def _naive_day_copy_predict(
    y_train: pd.Series, target_index: pd.DatetimeIndex
) -> np.ndarray:
    lookup = y_train.to_dict()
    preds: list[float] = []
    for ts in target_index:
        fallback = ts - timedelta(days=1)
        preds.append(float(lookup.get(fallback, y_train.iloc[-1])))
    return np.asarray(preds)


def _median_profile_predict(
    y_train: pd.Series, target_index: pd.DatetimeIndex
) -> np.ndarray:
    profile = y_train.groupby(
        [y_train.index.dayofweek, y_train.index.hour, y_train.index.minute]
    ).median()
    fallback = float(y_train.median())
    preds: list[float] = []
    for ts in target_index:
        key = (ts.dayofweek, ts.hour, ts.minute)
        preds.append(float(profile.get(key, fallback)))
    return np.asarray(preds)


def _linear_regression_predict(
    y_train: pd.Series,
    y_all: pd.Series,
    train_idx: np.ndarray,
    test_idx: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    features_all = _build_feature_table(y_all)
    valid_mask = features_all.notna().all(axis=1)
    valid_indices = np.where(valid_mask.to_numpy())[0]
    usable_train = np.intersect1d(train_idx, valid_indices)
    usable_test = np.intersect1d(test_idx, valid_indices)
    if len(usable_train) == 0 or len(usable_test) == 0:
        raise ValueError("Insufficient lag history for linear regression fold.")
    model = LinearRegression()
    x_train = features_all.iloc[usable_train]
    y_train_vec = y_all.iloc[usable_train]
    model.fit(x_train, y_train_vec)
    train_pred = model.predict(x_train)
    test_pred = model.predict(features_all.iloc[usable_test])
    return train_pred, test_pred


def _linear_regression_row_from_history(
    history: pd.Series, ts: pd.Timestamp
) -> pd.DataFrame:
    if len(history) < 96:
        raise ValueError("Not enough history to build linear-regression lag features.")
    return pd.DataFrame(
        {
            "lag_1": [float(history.iloc[-1])],
            "lag_4": [float(history.iloc[-4])],
            "lag_96": [float(history.iloc[-96])],
            "hour_sin": [np.sin(2 * np.pi * ts.hour / 24)],
            "hour_cos": [np.cos(2 * np.pi * ts.hour / 24)],
            "dow_sin": [np.sin(2 * np.pi * ts.dayofweek / 7)],
            "dow_cos": [np.cos(2 * np.pi * ts.dayofweek / 7)],
        },
        index=[ts],
    )


def _compute_single_model(
    model_name: str,
    series: pd.DataFrame,
    n_splits: int,
    gap: int,
    test_size: int,
) -> dict[str, object]:
    """
    Compute model results with a dual-purpose flow:

    1) Cross-validation phase (TimeSeriesSplit):
       - `splitter` folds are used to compute evaluation metrics (`fold_scores`),
         for all supported models.

    2) Display/export phase (fixed operational window):
       - After CV, predictions for charts/CSV are recomputed on:
         - in-sample: last 24h of input data
         - out-of-sample: next 24h forecast
       - This means chart/export predictions are intentionally independent from
         CV fold predictions.

    Example implication for `simple_copy`:
    - CV scoring uses fold-based predictions inside the `splitter` loop.
    - Chart/export uses `_naive_day_copy_predict` on the fixed final window.
    """
    logger.info(
        "enter _compute_single_model model=%s n_splits=%s gap=%s test_size=%s",
        model_name,
        n_splits,
        gap,
        test_size,
    )
    if model_name in {"arima", "lstm"}:
        raise NotImplementedError(
            f"Model '{model_name}' is not implemented yet in this repository."
        )
    y = series.set_index("measured_at_utc")["target"]
    splitter = TimeSeriesSplit(n_splits=n_splits, gap=gap, test_size=test_size)
    fold_scores: list[dict[str, float]] = []
    fold_details: list[dict[str, object]] = []
    last_residual: pd.DataFrame | None = None
    export_rows: list[dict[str, str | float | None]] = []
    features_all = (
        _build_feature_table(y) if model_name == "linear_regression" else None
    )
    valid_feature_indices = (
        np.where(features_all.notna().all(axis=1).to_numpy())[0]
        if features_all is not None
        else None
    )

    for train_idx, test_idx in splitter.split(y):
        fold_start = _now_utc()
        fold_number = len(fold_details) + 1
        y_train = y.iloc[train_idx]
        y_test = y.iloc[test_idx]
        split_train_start = y_train.index.min()
        split_train_end = y_train.index.max()
        split_test_start = y_test.index.min()
        split_test_end = y_test.index.max()
        split_test_std = float(y_test.std(ddof=0)) if len(y_test) > 0 else None
        if model_name == "simple_copy":
            # CV scoring is causal: test predictions use train fold only.
            out_pred = _naive_day_copy_predict(y_train, y_test.index)
        elif model_name == "median_copy":
            # CV scoring is causal: profile is fitted from past train fold only.
            out_pred = _median_profile_predict(y_train, y_test.index)
        elif model_name == "linear_regression":
            _in_pred_unused, out_pred = _linear_regression_predict(
                y_train, y, train_idx, test_idx
            )
            assert valid_feature_indices is not None
            y_train = y.iloc[np.intersect1d(train_idx, valid_feature_indices)]
            y_test = y.iloc[np.intersect1d(test_idx, valid_feature_indices)]
        else:
            raise ValueError(f"Unknown model: {model_name}")
        train_seconds = (_now_utc() - fold_start).total_seconds()
        y_true = y_test.to_numpy(dtype=float)
        y_pred = np.asarray(out_pred, dtype=float)
        fold_metric = _score_fold(y_true, y_pred, train_seconds)
        fold_scores.append(fold_metric)
        fold_details.append(
            {
                "fold": fold_number,
                "train_start": str(split_train_start),
                "train_end": str(split_train_end),
                "test_start": str(split_test_start),
                "test_end": str(split_test_end),
                "test_std": split_test_std,
                "model_rmse": {model_name: fold_metric["rmse"]},
            }
        )
        residuals = y_true - y_pred
        last_residual = pd.DataFrame(
            {
                "timestamp": y_test.index.astype(str),
                "residual": residuals,
            }
        )

    if last_residual is None:
        raise ValueError("No fold generated. Check TimeSeriesSplit parameters.")

    # NOTE:
    # The following plotting/export block intentionally does NOT reuse CV fold
    # predictions. It creates an operational view window:
    # - last day of observed input (in-sample display)
    # - next day horizon (out-of-sample forecast)
    # CV remains the source of aggregated metrics only.
    # Chart limits requested: last day of input as in-sample + one additional day forecast.
    in_sample_idx = y.index[-96:]
    full_input_idx = y.index
    out_sample_idx = pd.date_range(
        start=y.index[-1] + pd.Timedelta(minutes=15),
        periods=96,
        freq="15min",
        tz=y.index.tz,
    )
    if model_name == "simple_copy":
        history = y.loc[y.index < in_sample_idx[0]].copy()
        in_sample_pred_values: list[float] = []
        for ts in in_sample_idx:
            pred = float(_naive_day_copy_predict(history, pd.DatetimeIndex([ts]))[0])
            in_sample_pred_values.append(pred)
            # reveal actual only after prediction => no self-leakage
            history.loc[ts] = float(y.loc[ts])
        in_sample_pred = np.asarray(in_sample_pred_values, dtype=float)

        out_preds: list[float] = []
        for ts in out_sample_idx:
            pred = float(_naive_day_copy_predict(history, pd.DatetimeIndex([ts]))[0])
            out_preds.append(pred)
            history.loc[ts] = pred
        out_sample_pred = np.asarray(out_preds, dtype=float)
    elif model_name == "median_copy":
        history = y.loc[y.index < in_sample_idx[0]].copy()
        in_sample_pred_values: list[float] = []
        for ts in in_sample_idx:
            pred = float(_median_profile_predict(history, pd.DatetimeIndex([ts]))[0])
            in_sample_pred_values.append(pred)
            # reveal actual only after prediction => no self-leakage
            history.loc[ts] = float(y.loc[ts])
        in_sample_pred = np.asarray(in_sample_pred_values, dtype=float)

        out_preds: list[float] = []
        for ts in out_sample_idx:
            pred = float(_median_profile_predict(history, pd.DatetimeIndex([ts]))[0])
            out_preds.append(pred)
            history.loc[ts] = pred
        out_sample_pred = np.asarray(out_preds, dtype=float)
    elif model_name == "linear_regression":
        history = y.loc[y.index < in_sample_idx[0]].copy()
        in_preds: list[float] = []
        for ts in in_sample_idx:
            hist_features = _build_feature_table(history)
            valid_rows = hist_features.notna().all(axis=1)
            if not valid_rows.any():
                raise ValueError(
                    "Insufficient history for causal in-sample linear regression prediction."
                )
            model = LinearRegression()
            model.fit(hist_features.loc[valid_rows], history.loc[valid_rows])
            row = _linear_regression_row_from_history(history, ts)
            pred = float(model.predict(row)[0])
            in_preds.append(pred)
            # reveal actual only after prediction => no self-leakage
            history.loc[ts] = float(y.loc[ts])
        in_sample_pred = np.asarray(in_preds, dtype=float)

        out_preds: list[float] = []
        for ts in out_sample_idx:
            hist_features = _build_feature_table(history)
            valid_rows = hist_features.notna().all(axis=1)
            if not valid_rows.any():
                raise ValueError(
                    "Insufficient history for causal out-of-sample linear regression prediction."
                )
            model = LinearRegression()
            model.fit(hist_features.loc[valid_rows], history.loc[valid_rows])
            row = _linear_regression_row_from_history(history, ts)
            pred = float(model.predict(row)[0])
            out_preds.append(pred)
            history.loc[ts] = pred
        out_sample_pred = np.asarray(out_preds)
    else:
        raise ValueError(f"Unknown model: {model_name}")

    # Show full input/training history in charts/exports:
    # - `actual` for all input points
    # - `predicted` only on the last-day in-sample window
    in_sample_pred_series = pd.Series(index=full_input_idx, dtype=float)
    in_sample_pred_series.loc[in_sample_idx] = np.asarray(in_sample_pred, dtype=float)
    in_sample_chart = []
    for ts in full_input_idx:
        predicted = in_sample_pred_series.loc[ts]
        in_sample_chart.append(
            {
                "timestamp": str(ts),
                "actual": float(y.loc[ts]),
                "predicted": (None if pd.isna(predicted) else float(predicted)),
            }
        )
    out_of_sample_chart = [
        {
            "timestamp": str(ts),
            "actual": None,
            "predicted": float(pred),
        }
        for ts, pred in zip(out_sample_idx, out_sample_pred)
    ]
    residual_chart = [
        {
            "timestamp": str(ts),
            "residual": float(actual - pred),
        }
        for ts, actual, pred in zip(
            in_sample_idx,
            y.loc[in_sample_idx].to_numpy(dtype=float),
            np.asarray(in_sample_pred, dtype=float),
        )
    ]

    in_sample_window_ts = set(in_sample_idx.astype(str))
    for row in in_sample_chart:
        export_rows.append(
            {
                "timestamp": row["timestamp"],
                "segment": (
                    "in_sample_window"
                    if row["timestamp"] in in_sample_window_ts
                    else "training_input"
                ),
                "actual": float(row["actual"]),
                "predicted": (
                    None if row["predicted"] is None else float(row["predicted"])
                ),
            }
        )
    for row in out_of_sample_chart:
        export_rows.append(
            {
                "timestamp": row["timestamp"],
                "segment": "out_of_sample",
                "actual": row["actual"],
                "predicted": float(row["predicted"]),
            }
        )
    export_rows.sort(
        key=lambda r: pd.to_datetime(str(r["timestamp"]), errors="coerce", utc=True)
    )

    return {
        "metrics": _json_safe(_aggregate_scores(fold_scores)),
        "fold_details": _json_safe(fold_details),
        "in_sample_chart": _json_safe(in_sample_chart),
        "out_of_sample_chart": _json_safe(out_of_sample_chart),
        "residual_chart": _json_safe(residual_chart),
        "export_rows": export_rows,
    }


class ForecastManager:
    def __init__(self, data_root: Path) -> None:
        self._data_root = data_root
        self._runs: dict[str, ForecastRun] = {}
        self._schedules: dict[str, ForecastSchedule] = {}
        self._site_queue: dict[str, deque[str]] = defaultdict(deque)
        self._site_active: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._dispatcher_task: asyncio.Task | None = None
        self._scheduler_task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        self._stop.clear()
        if self._dispatcher_task is None:
            self._dispatcher_task = asyncio.create_task(self._dispatcher_loop())
        if self._scheduler_task is None:
            self._scheduler_task = asyncio.create_task(self._scheduler_loop())

    async def stop(self) -> None:
        self._stop.set()
        for task in [self._dispatcher_task, self._scheduler_task]:
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._dispatcher_task = None
        self._scheduler_task = None

    async def create_run(
        self,
        payload: RunCreateRequest,
        trigger_source: Literal["manual", "scheduled"] = "manual",
    ) -> ForecastRun:
        logger.info(
            "enter create_run site=%s model=%s source=%s",
            payload.site,
            payload.model,
            trigger_source,
        )
        site = payload.site.lower().strip()
        if site not in _discover_sites(self._data_root):
            raise HTTPException(
                status_code=404, detail=f"Unknown site '{payload.site}'."
            )
        run = ForecastRun(
            run_id=str(uuid.uuid4()),
            site=site,
            model=payload.model,
            n_splits=payload.n_splits,
            gap=payload.gap,
            test_size=payload.test_size,
            trigger_source=trigger_source,
            status="queued",
            created_at=_now_utc(),
        )
        async with self._lock:
            self._runs[run.run_id] = run
            queue = self._site_queue[site]
            queue.append(run.run_id)
            self._recompute_queue_positions(site)
        return run

    async def list_runs(
        self, site: str | None = None, status: RUN_STATUSES | None = None
    ) -> list[ForecastRun]:
        logger.info("enter list_runs site=%s status=%s", site, status)
        async with self._lock:
            runs = list(self._runs.values())
        if site:
            runs = [r for r in runs if r.site == site.lower()]
        if status:
            runs = [r for r in runs if r.status == status]
        runs.sort(key=lambda r: r.created_at, reverse=True)
        return runs

    async def get_run(self, run_id: str) -> ForecastRun:
        logger.info("enter get_run run_id=%s", run_id)
        async with self._lock:
            run = self._runs.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"Unknown run '{run_id}'.")
        return run

    async def create_schedule(self, payload: ScheduleCreateRequest) -> ForecastSchedule:
        logger.info(
            "enter create_schedule site=%s model=%s", payload.site, payload.model
        )
        schedule = ForecastSchedule(
            schedule_id=str(uuid.uuid4()),
            site=payload.site.lower().strip(),
            model=payload.model,
            n_splits=payload.n_splits,
            gap=payload.gap,
            test_size=payload.test_size,
            active=payload.active,
            trigger_time=time(hour=9, minute=0),
            timezone="Europe/Paris",
        )
        if schedule.site not in _discover_sites(self._data_root):
            raise HTTPException(
                status_code=404, detail=f"Unknown site '{payload.site}'."
            )
        async with self._lock:
            self._schedules[schedule.schedule_id] = schedule
        return schedule

    async def update_schedule(
        self, schedule_id: str, payload: ScheduleUpdateRequest
    ) -> ForecastSchedule:
        logger.info("enter update_schedule schedule_id=%s", schedule_id)
        site = payload.site.lower().strip()
        if site not in _discover_sites(self._data_root):
            raise HTTPException(
                status_code=404, detail=f"Unknown site '{payload.site}'."
            )
        async with self._lock:
            schedule = self._schedules.get(schedule_id)
            if schedule is None:
                raise HTTPException(
                    status_code=404, detail=f"Unknown schedule '{schedule_id}'."
                )
            schedule.site = site
            schedule.model = payload.model
            schedule.n_splits = payload.n_splits
            schedule.gap = payload.gap
            schedule.test_size = payload.test_size
            schedule.active = payload.active
        return schedule

    async def list_schedules(self) -> list[ForecastSchedule]:
        async with self._lock:
            values = list(self._schedules.values())
        values.sort(key=lambda s: s.schedule_id)
        return values

    async def set_schedule_active(
        self, schedule_id: str, active: bool
    ) -> ForecastSchedule:
        logger.info(
            "enter set_schedule_active schedule_id=%s active=%s", schedule_id, active
        )
        async with self._lock:
            schedule = self._schedules.get(schedule_id)
            if schedule is None:
                raise HTTPException(
                    status_code=404, detail=f"Unknown schedule '{schedule_id}'."
                )
            schedule.active = active
        return schedule

    async def delete_schedule(self, schedule_id: str) -> None:
        logger.info("enter delete_schedule schedule_id=%s", schedule_id)
        async with self._lock:
            removed = self._schedules.pop(schedule_id, None)
            if removed is None:
                raise HTTPException(
                    status_code=404, detail=f"Unknown schedule '{schedule_id}'."
                )

    def available_sites(self) -> list[str]:
        return _discover_sites(self._data_root)

    async def _dispatcher_loop(self) -> None:
        logger.info("enter _dispatcher_loop")
        while not self._stop.is_set():
            await asyncio.sleep(0.3)
            launch_site: str | None = None
            launch_run: str | None = None
            async with self._lock:
                for site, queue in self._site_queue.items():
                    if not queue or site in self._site_active:
                        continue
                    launch_run = queue.popleft()
                    launch_site = site
                    self._site_active[site] = launch_run
                    self._recompute_queue_positions(site)
                    run = self._runs[launch_run]
                    run.status = "running"
                    run.started_at = _now_utc()
                    break
            if launch_run is None or launch_site is None:
                continue
            asyncio.create_task(self._execute_run(launch_site, launch_run))

    async def _execute_run(self, site: str, run_id: str) -> None:
        logger.info("enter _execute_run site=%s run_id=%s", site, run_id)
        try:
            async with self._lock:
                run = self._runs[run_id]
            logger.info("_execute_run run_id=%s step=load_series", run_id)
            series = await asyncio.to_thread(
                _load_site_timeseries_from_workflow, self._data_root, site
            )
            model_names = (
                [
                    "simple_copy",
                    "median_copy",
                    "linear_regression",
                ]  # , "arima", "lstm" TODO add them later
                if run.model == "all_models"
                else [run.model]
            )
            ranking: list[dict[str, float]] = []
            per_model: dict[str, dict[str, object]] = {}
            logs: list[str] = []
            for model_name in model_names:
                logs.append(f"Running model={model_name}")
                logger.info(
                    "_execute_run run_id=%s step=compute_model model=%s",
                    run_id,
                    model_name,
                )
                result = await asyncio.to_thread(
                    _compute_single_model,
                    model_name,
                    series,
                    run.n_splits,
                    run.gap,
                    run.test_size,
                )
                per_model[model_name] = result
                metrics = result["metrics"]
                ranking.append({"model": model_name, "rmse": float(metrics["rmse"])})
            ranking.sort(key=lambda r: r["rmse"])
            selected_model = (
                ranking[0]["model"] if run.model == "all_models" else run.model
            )
            best = per_model[selected_model]
            scoring_details_map: dict[int, dict[str, object]] = {}
            for model_name, model_result in per_model.items():
                fold_details = model_result.get("fold_details", [])
                for row in fold_details:
                    fold_num = int(row["fold"])
                    if fold_num not in scoring_details_map:
                        scoring_details_map[fold_num] = {
                            "fold": fold_num,
                            "train_start": row["train_start"],
                            "train_end": row["train_end"],
                            "test_start": row["test_start"],
                            "test_end": row["test_end"],
                            "test_std": row["test_std"],
                            "model_rmse": {},
                        }
                    scoring_details_map[fold_num]["model_rmse"][model_name] = row[
                        "model_rmse"
                    ][model_name]
            scoring_details = [
                scoring_details_map[k] for k in sorted(scoring_details_map.keys())
            ]
            csv_content = io.StringIO()
            writer = csv.DictWriter(
                csv_content, fieldnames=["timestamp", "segment", "actual", "predicted"]
            )
            writer.writeheader()
            for row in best["export_rows"]:
                writer.writerow(row)
            async with self._lock:
                run = self._runs[run_id]
                run.status = "done"
                run.finished_at = _now_utc()
                run.metrics = _json_safe(best["metrics"])
                run.scoring_details = _json_safe(scoring_details)
                run.in_sample_chart = _json_safe(best["in_sample_chart"])
                run.out_of_sample_chart = _json_safe(best["out_of_sample_chart"])
                run.residual_chart = _json_safe(best["residual_chart"])
                run.ranking = _json_safe(
                    ranking
                    if run.model == "all_models"
                    else [
                        {
                            "model": selected_model,
                            "rmse": float(best["metrics"]["rmse"]),
                        }
                    ]
                )
                run.logs = "\n".join(logs)
                run.csv_buffer = csv_content.getvalue()
            logger.info("_execute_run run_id=%s status=done", run_id)
        except Exception as exc:  # noqa: BLE001
            async with self._lock:
                run = self._runs[run_id]
                run.status = "failed"
                run.finished_at = _now_utc()
                run.error = str(exc)
                run.logs = traceback.format_exc(limit=8)
            logger.exception(
                "_execute_run run_id=%s status=failed error=%s", run_id, exc
            )
        finally:
            async with self._lock:
                self._site_active.pop(site, None)

    async def _scheduler_loop(self) -> None:
        while not self._stop.is_set():
            await asyncio.sleep(20)
            now_local = datetime.now(PARIS_TZ)
            today = now_local.date()
            should_trigger = now_local.hour == 9 and now_local.minute == 0
            if not should_trigger:
                continue
            async with self._lock:
                schedules = list(self._schedules.values())
            for schedule in schedules:
                if not schedule.active:
                    continue
                last_date = (
                    schedule.last_triggered_at.astimezone(PARIS_TZ).date()
                    if schedule.last_triggered_at
                    else None
                )
                if last_date == today:
                    continue
                payload = RunCreateRequest(
                    site=schedule.site,
                    model=schedule.model,
                    n_splits=schedule.n_splits,
                    gap=schedule.gap,
                    test_size=schedule.test_size,
                )
                await self.create_run(payload, trigger_source="scheduled")
                async with self._lock:
                    schedule.last_triggered_at = _now_utc()

    def _recompute_queue_positions(self, site: str) -> None:
        queue = self._site_queue[site]
        for idx, run_id in enumerate(queue, start=1):
            self._runs[run_id].queue_position = idx


def _to_summary(run: ForecastRun) -> RunSummaryResponse:
    return RunSummaryResponse(
        run_id=run.run_id,
        site=run.site,
        model=run.model,
        trigger_source=run.trigger_source,
        status=run.status,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        queue_position=run.queue_position,
    )


def _to_detail(run: ForecastRun) -> RunDetailResponse:
    base = _to_summary(run)
    return RunDetailResponse(
        **base.model_dump(),
        n_splits=run.n_splits,
        gap=run.gap,
        test_size=run.test_size,
        ranking=run.ranking,
        metrics=run.metrics,
        scoring_details=run.scoring_details,
        in_sample_chart=run.in_sample_chart,
        out_of_sample_chart=run.out_of_sample_chart,
        residual_chart=run.residual_chart,
        logs=run.logs,
        error=run.error,
    )


def build_forecast_router(manager: ForecastManager) -> APIRouter:
    router = APIRouter(prefix="/forecasts", tags=["forecasts"])

    @router.get("/tab")
    async def forecasts_tab() -> FileResponse:
        if not FORECAST_TAB_HTML.exists():
            raise HTTPException(
                status_code=500, detail="Forecast UI assets are missing."
            )
        return FileResponse(FORECAST_TAB_HTML)

    @router.get("/sites")
    async def list_sites() -> dict[str, list[str]]:
        return {"sites": manager.available_sites()}

    @router.post("/runs", response_model=RunSummaryResponse)
    async def create_run(payload: RunCreateRequest) -> RunSummaryResponse:
        run = await manager.create_run(payload, trigger_source="manual")
        return _to_summary(run)

    @router.get("/runs", response_model=list[RunSummaryResponse])
    async def list_runs(
        site: str | None = None, status: RUN_STATUSES | None = None
    ) -> list[RunSummaryResponse]:
        runs = await manager.list_runs(site=site, status=status)
        return [_to_summary(r) for r in runs]

    @router.get("/runs/{run_id}", response_model=RunDetailResponse)
    async def get_run(run_id: str) -> RunDetailResponse:
        run = await manager.get_run(run_id)
        return _to_detail(run)

    @router.get("/runs/{run_id}/export")
    async def export_run(run_id: str) -> StreamingResponse:
        run = await manager.get_run(run_id)
        if run.status != "done" or not run.csv_buffer:
            raise HTTPException(
                status_code=409, detail="Run result not available for export."
            )
        buf = io.BytesIO(run.csv_buffer.encode("utf-8"))
        created = run.created_at.astimezone(PARIS_TZ).strftime("%Y%m%d_%H%M%S")
        filename = (
            f"forecast_{run.site}_{created}_{run.model}"
            f"_ns{run.n_splits}_g{run.gap}_ts{run.test_size}.csv"
        )
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return StreamingResponse(buf, media_type="text/csv", headers=headers)

    @router.post("/schedules", response_model=ScheduleResponse)
    async def create_schedule(payload: ScheduleCreateRequest) -> ScheduleResponse:
        schedule = await manager.create_schedule(payload)
        return ScheduleResponse(
            schedule_id=schedule.schedule_id,
            site=schedule.site,
            model=schedule.model,
            n_splits=schedule.n_splits,
            gap=schedule.gap,
            test_size=schedule.test_size,
            active=schedule.active,
            trigger_time=schedule.trigger_time.isoformat(timespec="minutes"),
            timezone=schedule.timezone,
            last_triggered_at=schedule.last_triggered_at,
        )

    @router.patch("/schedules/{schedule_id}", response_model=ScheduleResponse)
    async def update_schedule(
        schedule_id: str, payload: ScheduleUpdateRequest
    ) -> ScheduleResponse:
        schedule = await manager.update_schedule(schedule_id, payload)
        return ScheduleResponse(
            schedule_id=schedule.schedule_id,
            site=schedule.site,
            model=schedule.model,
            n_splits=schedule.n_splits,
            gap=schedule.gap,
            test_size=schedule.test_size,
            active=schedule.active,
            trigger_time=schedule.trigger_time.isoformat(timespec="minutes"),
            timezone=schedule.timezone,
            last_triggered_at=schedule.last_triggered_at,
        )

    @router.get("/schedules", response_model=list[ScheduleResponse])
    async def list_schedules() -> list[ScheduleResponse]:
        schedules = await manager.list_schedules()
        return [
            ScheduleResponse(
                schedule_id=s.schedule_id,
                site=s.site,
                model=s.model,
                n_splits=s.n_splits,
                gap=s.gap,
                test_size=s.test_size,
                active=s.active,
                trigger_time=s.trigger_time.isoformat(timespec="minutes"),
                timezone=s.timezone,
                last_triggered_at=s.last_triggered_at,
            )
            for s in schedules
        ]

    @router.patch("/schedules/{schedule_id}/active", response_model=ScheduleResponse)
    async def set_schedule_active(
        schedule_id: str, payload: ScheduleActiveUpdateRequest
    ) -> ScheduleResponse:
        schedule = await manager.set_schedule_active(schedule_id, payload.active)
        return ScheduleResponse(
            schedule_id=schedule.schedule_id,
            site=schedule.site,
            model=schedule.model,
            n_splits=schedule.n_splits,
            gap=schedule.gap,
            test_size=schedule.test_size,
            active=schedule.active,
            trigger_time=schedule.trigger_time.isoformat(timespec="minutes"),
            timezone=schedule.timezone,
            last_triggered_at=schedule.last_triggered_at,
        )

    @router.delete("/schedules/{schedule_id}")
    async def delete_schedule(schedule_id: str) -> dict[str, str]:
        await manager.delete_schedule(schedule_id)
        return {"status": "deleted"}

    return router
