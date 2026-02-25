import pandas as pd
import pytest

from src.predict import copy_median_values

def test_copy_median_values_extends_one_day_with_overall_median_when_no_grouping() -> None:
    df = pd.DataFrame(
        {
            "timestamp_col": pd.date_range("2026-01-01 00:00:00", periods=4, freq="1h", tz="UTC"),
            "value_col": [1.0, 3.0, 5.0, 7.0],
        }
    )

    result = copy_median_values(
        df=df,
        timestamp_col="timestamp_col",
        value_col="value_col",
        respect_holidays=False,
        respect_weekdays=False,
        respect_time=False,
        extension="jour",
    )

    new_rows = result.iloc[len(df):]
    assert len(result) == len(df) + 24
    assert new_rows["timestamp_col"].iloc[0] == pd.Timestamp("2026-01-01 04:00:00", tz="UTC")
    assert new_rows["value_col"].tolist() == pytest.approx([4.0] * len(new_rows))


def test_copy_median_values_rejects_invalid_extension() -> None:
    df = pd.DataFrame(
        {
            "timestamp_col": pd.date_range("2026-01-01 00:00:00", periods=4, freq="1h", tz="UTC"),
            "value_col": [1.0, 3.0, 5.0, 7.0],
        }
    )

    with pytest.raises(ValueError, match="extension must be 'jour' or 'semaine'"):
        copy_median_values(
            df=df,
            timestamp_col="timestamp_col",
            value_col="value_col",
            respect_holidays=False,
            respect_weekdays=False,
            respect_time=False,
            extension="month",
        )


def test_copy_median_values_rejects_inconsistent_sampling_interval() -> None:
    df = pd.DataFrame(
        {
            "timestamp_col": pd.to_datetime(
                [
                    "2026-01-01 00:00:00+00:00",
                    "2026-01-01 00:15:00+00:00",
                    "2026-01-01 00:45:00+00:00",
                ]
            ),
            "value_col": [1.0, 2.0, 3.0],
        }
    )

    with pytest.raises(ValueError, match="inconsistent"):
        copy_median_values(
            df=df,
            timestamp_col="timestamp_col",
            value_col="value_col",
            respect_holidays=False,
            respect_weekdays=False,
            respect_time=False,
            extension="jour",
        )