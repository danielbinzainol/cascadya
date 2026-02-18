import pandas as pd

def analyze(df: pd.DataFrame,
            timestamp_col: str = "measured_at_utc",
            timestamp_diff_col: str = "timestamp_diff_col"):
    df = df.copy()
    df = df.reset_index()
    df[timestamp_diff_col] = df[timestamp_col].diff()
    hist = (df[timestamp_diff_col] / pd.Timedelta(minutes = 1)).hist(log=True)

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

    anomalies_mask = elapsed.notna() & ((elapsed < expected_delta * 0.9) | (elapsed > expected_delta * 1.1))
    elapsed_anomalies = df.loc[anomalies_mask, [timestamp_col]].copy()
    elapsed_anomalies["Previous timestamp"] = df[timestamp_col].shift(1)
    elapsed_anomalies["Elapsed"] = elapsed[anomalies_mask]
    elapsed_anomalies["Expected elapsed"] = expected_delta

    print(
        "---------------- elapsed anomalies : "
        f"{len(elapsed_anomalies)} (expected {expected_delta}) ------------"
    )

    return elapsed_anomalies, expected_delta


# timestamp_diff_col va jusqu'a 1h29, donc ~80 minutes, la plus grande "bin" de l'histogramme
def resample(df: pd.DataFrame,
             timestamp_col: str = "measured_at_utc",
             desired_timedelta: str = "1h",
             aggregate_function: str = "sum") -> pd.DataFrame:
    df = df.copy()
    df = df.set_index(timestamp_col)

    # downsample
    df = df.resample(desired_timedelta).apply(aggregate_function).reset_index()

    return df