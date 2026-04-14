from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.model_selection import TimeSeriesSplit

from src.dataset import (
    add_missing_timestamps_with_previous_value,
    equivalent_constant_rate_on_15min,
)
from src.ingest import data_workflow
from src.ml_models.forecasts.schemas import MODEL_NAME, RUN_STATUSES

PARIS_TZ = ZoneInfo("Europe/Paris")
FORECAST_TAB_HTML = (
    Path(__file__).resolve().parents[3] / "static" / "forecasts" / "index.html"
)
ALLOWED_SITES: tuple[str, ...] = ("inariz",)

logger = logging.getLogger("forecast_backoffice")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("[forecast_backoffice] %(asctime)s %(levelname)s %(message)s")
    )
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


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
        "inariz_steam_prod_2026-03-01_to_2026-03-04.csv",
        "inariz_steam_prod_2026-03-05_to_2026-03-08.csv",
        "inariz_steam_prod_2026-03-09_to_2026-03-12.csv",
        "inariz_steam_prod_2026-03-13_to_2026-03-16.csv",
        "inariz_steam_prod_2026-03-17_to_2026-03-20.csv",
        "inariz_steam_prod_2026-03-21_to_2026-03-24.csv",
        "inariz_steam_prod_2026-03-25_to_2026-03-28.csv",
        "inariz_steam_prod_2026-03-29_to_2026-03-31.csv",
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
            out_pred = _naive_day_copy_predict(y_train, y_test.index)
        elif model_name == "median_copy":
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
            {"timestamp": y_test.index.astype(str), "residual": residuals}
        )

    if last_residual is None:
        raise ValueError("No fold generated. Check TimeSeriesSplit parameters.")

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
        {"timestamp": str(ts), "actual": None, "predicted": float(pred)}
        for ts, pred in zip(out_sample_idx, out_sample_pred)
    ]
    residual_chart = [
        {"timestamp": str(ts), "residual": float(actual - pred)}
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
                "segment": "in_sample_window"
                if row["timestamp"] in in_sample_window_ts
                else "training_input",
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
