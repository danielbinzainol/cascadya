import pandas as pd


def analyze(
    df: pd.DataFrame,
    timestamp_col: str = "measured_at_utc",
    timestamp_diff_col: str = "timestamp_diff_col",
):
    df = df.reset_index()
    df[timestamp_diff_col] = df[timestamp_col].diff()
    _ = (df[timestamp_diff_col] / pd.Timedelta(minutes=1)).hist(log=True)

    print(df[timestamp_diff_col].describe())


def detect_elapsed_time_anomalies(
    df: pd.DataFrame,
    timestamp_col: str = "measured_at_utc",
) -> tuple[pd.DataFrame, pd.Timedelta]:
    # todo simplifier, est-ce que ces 3 actions ne reviennent qu'à faire du dropna?
    timestamps = pd.to_datetime(
        df[timestamp_col],
        errors="coerce",
        dayfirst=True,
    )
    df = df.assign(**{timestamp_col: timestamps}).dropna(subset=[timestamp_col])
    df = df.sort_values(timestamp_col)

    elapsed = df[timestamp_col].diff()
    expected = elapsed.dropna().mode()
    expected_delta = expected.iloc[0] if not expected.empty else pd.Timedelta(0)

    anomalies_mask = elapsed.notna() & (
        (elapsed < expected_delta * 0.9) | (elapsed > expected_delta * 1.1)
    )
    elapsed_anomalies = df.loc[anomalies_mask, [timestamp_col]].copy()
    elapsed_anomalies["Previous timestamp"] = df[timestamp_col].shift(1)
    elapsed_anomalies["Elapsed"] = elapsed[anomalies_mask]
    elapsed_anomalies["Expected elapsed"] = expected_delta

    print(
        "---------------- elapsed anomalies : "
        f"{len(elapsed_anomalies)} (expected {expected_delta}) ------------"
    )

    return elapsed_anomalies, expected_delta


def resample(
    df: pd.DataFrame,
    timestamp_col: str = "measured_at_utc",
    desired_timedelta: str = "15min",
    aggregate_function: str = "sum",
) -> pd.DataFrame:
    df = df.copy()
    df = df.set_index(timestamp_col)

    df = df.resample(desired_timedelta).apply(aggregate_function).reset_index()

    return df


def add_missing_timestamps_with_previous_value(
    df: pd.DataFrame,
    timestamp_col: str = "measured_at_utc",
    value_col: str = "steam_production_m3_h",
    freq: str = "15min",
) -> pd.DataFrame:
    """Add missing grid timestamps while preserving original timestamps.

    The function:
    - Parses and sorts timestamps.
    - Keeps the last observation when duplicate timestamps exist.
    - Builds a complete date range between min and max at `freq`.
    - Adds only the missing grid timestamps (does not drop original irregular ones).
    - Forward-fills `value_col` so newly inserted timestamps copy the previous value.
    """
    if timestamp_col not in df.columns:
        raise KeyError(f"Missing timestamp column: {timestamp_col}")
    if value_col not in df.columns:
        raise KeyError(f"Missing value column: {value_col}")

    out = df.copy()
    out[timestamp_col] = pd.to_datetime(out[timestamp_col], errors="coerce")
    out = out.dropna(subset=[timestamp_col]).sort_values(timestamp_col)

    # If duplicates exist at the same timestamp, keep the last available value.
    out = out.drop_duplicates(subset=[timestamp_col], keep="last")

    if out.empty:
        return out

    start = out[timestamp_col].min().floor(freq)
    end = out[timestamp_col].max().ceil(freq)
    full_index = pd.date_range(start=start, end=end, freq=freq)

    out = out.set_index(timestamp_col)
    combined_index = out.index.union(full_index).sort_values()
    out = out.reindex(combined_index)
    out[value_col] = out[value_col].ffill()
    out.index.name = timestamp_col

    return out.reset_index()


def equivalent_constant_rate_on_15min(
    df: pd.DataFrame,
    timestamp_col: str = "measured_at_utc",
    value_col: str = "steam_production_m3_h",
    freq: str = "15min",
) -> pd.DataFrame:
    """Return input rows extended with interval and equivalent-rate columns."""
    if timestamp_col not in df.columns:
        raise KeyError(f"Missing timestamp column: {timestamp_col}")
    if value_col not in df.columns:
        raise KeyError(f"Missing value column: {value_col}")

    out = df.copy()
    out[timestamp_col] = pd.to_datetime(out[timestamp_col], errors="coerce")
    out = out.dropna(subset=[timestamp_col]).sort_values(timestamp_col)

    if out.empty:
        for col in [
            "elapsed_seconds",
            "duration_hours",
            "interval_rate_m3_h",
            "volume_m3",
            "interval_start",
            "bin_start",
            "equivalent_steam_production_m3_h",
        ]:
            out[col] = pd.NA
        return out

    original = out.copy()
    work = out.drop_duplicates(subset=[timestamp_col], keep="last").set_index(
        timestamp_col
    )
    grid = pd.date_range(
        start=work.index.min(),
        end=work.index.max().ceil(freq),
        freq=freq,
    )
    work = work.reindex(work.index.union(grid).sort_values())
    work[value_col] = work[value_col].ffill()

    # Intervals are interpreted as (previous_timestamp, current_timestamp].
    intervals = work.copy()
    intervals["elapsed_seconds"] = (
        intervals.index.to_series().diff().dt.total_seconds().fillna(0.0)
    )
    intervals["duration_hours"] = intervals["elapsed_seconds"] / 3600.0
    intervals["interval_rate_m3_h"] = intervals[value_col].shift(1)
    intervals["volume_m3"] = (
        intervals["duration_hours"] * intervals["interval_rate_m3_h"]
    )
    intervals["interval_start"] = intervals.index.to_series().shift(1)
    intervals["bin_start"] = intervals["interval_start"].dt.floor(freq)
    intervals.index.name = timestamp_col

    intervals_df = intervals.reset_index()

    step_hours = pd.Timedelta(freq).total_seconds() / 3600.0
    equivalent = (
        intervals_df.dropna(subset=["volume_m3", "bin_start"])
        .groupby("bin_start", as_index=False)["volume_m3"]
        .sum()
    )
    equivalent["equivalent_steam_production_m3_h"] = (
        equivalent["volume_m3"] / step_hours
    )
    intervals_df = intervals_df.merge(
        equivalent[["bin_start", "equivalent_steam_production_m3_h"]],
        on="bin_start",
        how="left",
    )

    cols_to_keep = [
        timestamp_col,
        "elapsed_seconds",
        "duration_hours",
        "interval_rate_m3_h",
        "volume_m3",
        "interval_start",
        "bin_start",
        "equivalent_steam_production_m3_h",
    ]

    return original.merge(intervals_df[cols_to_keep], on=timestamp_col, how="left")
