import pandas as pd
import pytest

from src.dataset import resample

def test_resample_sums_values_on_30min_windows() -> None:
    df = pd.DataFrame(
        {
            "measured_at_utc": pd.date_range("2026-01-01 00:00:00", periods=4, freq="15min", tz="UTC"),
            "steam_production_kwhth": [1.0, 2.0, 3.0, 4.0],
        }
    )

    result = resample(
        df,
        timestamp_col="measured_at_utc",
        desired_timedelta="30min",
        aggregate_function="sum",
    )

    expected = pd.DataFrame(
        {
            "measured_at_utc": pd.to_datetime(
                ["2026-01-01 00:00:00+00:00", "2026-01-01 00:30:00+00:00"]
            ),
            "steam_production_kwhth": [3.0, 7.0],
        }
    )
    pd.testing.assert_frame_equal(result, expected)


def test_resample_supports_custom_timestamp_column_and_mean() -> None:
    df = pd.DataFrame(
        {
            "ts": pd.date_range("2026-01-01 00:00:00", periods=4, freq="15min", tz="UTC"),
            "a": [1.0, 2.0, 3.0, 4.0],
            "b": [10.0, 20.0, 30.0, 40.0],
        }
    )

    result = resample(
        df,
        timestamp_col="ts",
        desired_timedelta="1h",
        aggregate_function="mean",
    )

    assert len(result) == 1
    assert result.loc[0, "a"] == pytest.approx(2.5)
    assert result.loc[0, "b"] == pytest.approx(25.0)