from pathlib import Path
import pandas as pd
#
from utils import load_config

        
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

def parse_date_col(
    df: pd.DataFrame,
    date_col: str | None = None,
):
    if date_col is None:
        # Heuristic: pick the first column that parses as datetime well
        for col in df.columns:
            parsed = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
            if parsed.notna().mean() > 0.8:
                date_col = col
                df[col] = parsed
                break

    if not date_col:
        raise ValueError("Could not infer date column.")

    df = df.sort_values(date_col).set_index(date_col)
    y = df.reset_index(names="measured_at")

    if y.empty:
        raise ValueError("No numeric columns found to plot.")

    return y

def convert_timestamps_to_utc(
    df: pd.DataFrame,
    source_timezone: str | None,
    timestamp_col: str = "measured_at",
    local_col: str | None = None,
    tz_col: str = "source_timezone",
) -> pd.DataFrame:
    df = df.copy()
    timestamps = pd.to_datetime(df[timestamp_col], errors="coerce")
    if timestamps.dt.tz is None:
        if source_timezone is None:
            raise ValueError(f"source_timezone is required to localize timestamps. Not found in column '{timestamp_col}' nor provided as argument.")
        localized = timestamps.dt.tz_localize(source_timezone)
    else:
        localized = timestamps
    if local_col is None:
        local_col = f"{timestamp_col} (local time)"
    df[local_col] = localized
    df[timestamp_col] = localized.dt.tz_convert("UTC")
    df[tz_col] = str(source_timezone or localized.dt.tz)
    return df

def data_workflow(project: str):
    df = input_csv(project)
    y = parse_date_col(df)
    y = convert_timestamps_to_utc(y)

    config = load_config() 
    
    # give information on the frequency of the index:
    if "frequency" in config[project]["data"]:
        y = y.asfreq(config[project]["data"]["frequency"])
    
    return y