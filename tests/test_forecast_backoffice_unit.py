from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

import src.ml_models.forecasts.models as fb


def _make_series(periods: int = 320) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=periods, freq="15min", tz="UTC")
    values = np.sin(np.linspace(0, 12, periods)) * 100 + 500
    return pd.DataFrame({"measured_at_utc": idx, "target": values.astype(float)})


def test_discover_sites_is_fixed_allowed_list(tmp_path) -> None:
    (tmp_path / "data" / "anything").mkdir(parents=True, exist_ok=True)
    assert fb._discover_sites(tmp_path) == ["inariz"]


def test_json_safe_converts_non_finite_recursively() -> None:
    payload = {
        "a": float("nan"),
        "b": float("inf"),
        "c": [1.0, np.float64(-math.inf), {"x": np.float64(2.0)}],
    }
    out = fb._json_safe(payload)
    assert out["a"] is None
    assert out["b"] is None
    assert out["c"][1] is None
    assert out["c"][2]["x"] == 2.0


def test_safe_mape_handles_zero_targets_via_clipping() -> None:
    y_true = np.asarray([0.0, 2.0, 4.0])
    y_pred = np.asarray([1.0, 1.0, 3.0])
    mape = fb._safe_mape(y_true, y_pred)
    assert np.isfinite(mape)
    assert mape > 0


def test_aggregate_scores_means_all_metrics() -> None:
    scores = [
        {"mae": 1.0, "rmse": 2.0, "mape": 0.1, "r2": 0.5, "train_time_seconds": 1.0},
        {"mae": 3.0, "rmse": 4.0, "mape": 0.3, "r2": 0.7, "train_time_seconds": 3.0},
    ]
    out = fb._aggregate_scores(scores)
    assert out["mae"] == 2.0
    assert out["rmse"] == 3.0
    assert out["mape"] == 0.2
    assert out["r2"] == 0.6
    assert out["train_time_seconds"] == 2.0


def test_naive_day_copy_predict_uses_previous_day_or_last_value() -> None:
    idx = pd.date_range("2026-01-01", periods=4, freq="1D", tz="UTC")
    y_train = pd.Series([10.0, 20.0, 30.0, 40.0], index=idx)
    target = pd.DatetimeIndex(
        [
            pd.Timestamp("2026-01-05T00:00:00+00:00"),
            pd.Timestamp("2026-01-10T00:00:00+00:00"),
        ]
    )
    preds = fb._naive_day_copy_predict(y_train, target)
    # 2026-01-05 copies 2026-01-04 value
    assert preds[0] == 40.0
    # 2026-01-10 has no previous-day key in training dict => fallback to last train value
    assert preds[1] == 40.0


def test_median_profile_predict_uses_group_median_and_fallback() -> None:
    idx = pd.DatetimeIndex(
        [
            "2026-01-04 10:00:00+00:00",  # sunday
            "2026-01-11 10:00:00+00:00",  # sunday
            "2026-01-12 11:15:00+00:00",  # monday unique
        ]
    )
    y_train = pd.Series([10.0, 30.0, 50.0], index=idx)
    target = pd.DatetimeIndex(
        [
            "2026-01-18 10:00:00+00:00",  # same sunday slot => median(10,30)=20
            "2026-01-18 12:30:00+00:00",  # missing key => fallback global median 30
        ]
    )
    preds = fb._median_profile_predict(y_train, target)
    assert preds[0] == 20.0
    assert preds[1] == 30.0


def test_build_feature_table_contains_expected_columns() -> None:
    y = _make_series(140).set_index("measured_at_utc")["target"]
    x = fb._build_feature_table(y)
    assert set(x.columns) == {
        "lag_1",
        "lag_4",
        "lag_96",
        "hour_sin",
        "hour_cos",
        "dow_sin",
        "dow_cos",
    }
    # lag columns should contain NaN at start due to shifts
    assert x["lag_96"].isna().iloc[:96].all()


def test_linear_regression_row_from_history_requires_min_history() -> None:
    short_history = pd.Series(np.arange(10, dtype=float))
    with pytest.raises(ValueError, match="Not enough history"):
        fb._linear_regression_row_from_history(
            short_history, pd.Timestamp("2026-01-01T00:00:00+00:00")
        )


def test_linear_regression_row_from_history_feature_values() -> None:
    history = pd.Series(np.arange(120, dtype=float))
    ts = pd.Timestamp("2026-01-03T06:15:00+00:00")
    row = fb._linear_regression_row_from_history(history, ts)
    assert row.iloc[0]["lag_1"] == 119.0
    assert row.iloc[0]["lag_4"] == 116.0
    assert row.iloc[0]["lag_96"] == 24.0
    assert np.isfinite(row.iloc[0]["hour_sin"])
    assert np.isfinite(row.iloc[0]["dow_cos"])


@pytest.mark.parametrize(
    "model_name", ["simple_copy", "median_copy", "linear_regression"]
)
def test_compute_single_model_returns_expected_shapes(model_name: str) -> None:
    series = _make_series(420)
    out = fb._compute_single_model(
        model_name=model_name,
        series=series,
        n_splits=3,
        gap=0,
        test_size=96,
    )
    assert set(out.keys()) == {
        "metrics",
        "fold_details",
        "in_sample_chart",
        "out_of_sample_chart",
        "residual_chart",
        "export_rows",
    }
    assert len(out["fold_details"]) == 3
    assert len(out["in_sample_chart"]) >= 96
    assert len(out["out_of_sample_chart"]) == 96
    assert len(out["residual_chart"]) == 96
    timestamps = [pd.to_datetime(r["timestamp"], utc=True) for r in out["export_rows"]]
    assert timestamps == sorted(timestamps)


@pytest.mark.parametrize("model_name", ["arima", "lstm"])
def test_compute_single_model_raises_for_unimplemented(model_name: str) -> None:
    series = _make_series(300)
    with pytest.raises(NotImplementedError):
        fb._compute_single_model(
            model_name=model_name,
            series=series,
            n_splits=3,
            gap=0,
            test_size=96,
        )
