from pathlib import Path
import pandas as pd
#
from src.utils import load_config

        
def input_csv(project: str, **kwargs):
    config = load_config() 
    path = Path(__file__).resolve().parent.parent / Path(config[project]["data"]["path"])
    if not path.exists():
        raise FileNotFoundError(path)

    if "skiprows" in config[project]["data"]:
        kwargs.setdefault("skiprows", config[project]["data"]["skiprows"])
    if "usecols" in config[project]["data"]:
        kwargs.setdefault("usecols", config[project]["data"]["usecols"])

    df = pd.read_csv(path, sep=";", decimal=",", **kwargs)

    return df

def parse_timestamp_col(
    df: pd.DataFrame,
    timestamp_col: str | None = None,
    format: str = None,
):
    """
    Deactivated for now. 
    Might be useful if we don't know the timestamp_col or its format

    If timestamp_col is not provided:
    - loops through all columns, converts them to pandas Timseries, 
    - and if successful, breaks with the detected column.
    - transforms the detected date column into pandas Timeseries 
    - transformation is based on a format if provided. Otherwise, Dayfirst is assumed.
    If timestamp_col is provided: the column is transformed into a pandas Timeseries

    Then, the date col is sorted and given the "measured_at" name.
    """
    raise RuntimeError("This function is deactivated for now.")
    if timestamp_col is None:
        # Heuristic: pick the first column that parses correctly as a timestamp
        # hypothesis: in absence of format, assume dayfirst is True
        for col in df.columns:
            parsed = pd.to_datetime(df[col], errors="coerce", dayfirst=bool(format), format=format)
            if parsed.notna().mean() > 0.8:
                timestamp_col = col
                df[col] = parsed
                break
    else:
        df[timestamp_col] = pd.to_datetime(df[timestamp_col], errors="coerce", format=format)

    if not timestamp_col:
        raise ValueError("Could not infer date column.")

    df = df.sort_values(timestamp_col).set_index(timestamp_col)
    df = df.reset_index(names="measured_at")

    return df

def localize_and_convert_to_utc(
    df: pd.DataFrame,
    source_timezone: str | None,
    timestamp_col: str = "measured_at",
    local_col: str | None = None,
    tz_col: str = "source_timezone",
) -> pd.DataFrame:
    if df[timestamp_col].dt.tz is None:
        if source_timezone is None:
            raise ValueError(f"source_timezone is required to localize timestamps. Not found in column '{timestamp_col}' nor provided as argument.")
        localized = df[timestamp_col].dt.tz_localize(source_timezone)
    else:
        localized = df[timestamp_col]
    if local_col is None:
        local_col = f"{timestamp_col} (local time)"
    df[local_col] = localized
    df[timestamp_col] = localized.dt.tz_convert("UTC")
    df = df.rename(columns={timestamp_col: "measured_at_utc"})
    df[tz_col] = str(source_timezone or localized.tz.info)
    return df

def data_workflow(project: str):
    df = input_csv(project)

    config = load_config() 

    # parse timestamp_col, and rename
    timestamp_col = config[project]["data"]["timestamp_col"]
    timestamp_format = config[project]["data"]["timestamp_format"]
    df[timestamp_col] = pd.to_datetime(df[timestamp_col], errors="coerce", format=timestamp_format)
    df = df.sort_values(timestamp_col)
    df = df.rename(columns={timestamp_col: "measured_at"})

    # convert to UTC, and rename
    source_timezone = config[project]["data"]["timezone"]
    df = localize_and_convert_to_utc(df, source_timezone)

    # give information on the frequency of the index:
    if "frequency" in config[project]["data"]:
        df = df.asfreq(config[project]["data"]["frequency"])
    
    return df