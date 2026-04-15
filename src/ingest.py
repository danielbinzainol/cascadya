import os
from pathlib import Path, PureWindowsPath
import pandas as pd

#
from src.utils import load_config


def _normalize_config_dirpath(dirpath_value: str) -> Path:
    """Normalize config dir paths across Windows/Linux separators."""
    raw = dirpath_value.strip()
    if "\\" not in raw:
        return Path(raw)

    windows_parts = PureWindowsPath(raw).parts
    # Keep drive-based absolute Windows paths as-is (with normalized separators).
    if windows_parts and windows_parts[0].endswith(":\\"):
        return Path(raw.replace("\\", "/"))
    # Convert relative Windows-style paths into native Path segments.
    return Path(*windows_parts)


def _strip_data_prefix(path_obj: Path) -> Path:
    """Return path without a leading `data/` segment."""
    parts = path_obj.parts
    if parts and parts[0].lower() == "data":
        return Path(*parts[1:]) if len(parts) > 1 else Path(".")
    return path_obj


def _resolve_data_dir(project: str, configured_dir: Path) -> Path:
    """
    Resolve data directory with optional environment overrides.

    Supported env vars:
    - C_MARKET_DATA_ROOT: global data root (example: /app/data)
    - <PROJECT>_DATA_ROOT: project-specific data root (example: /mnt/inariz_data)
      where <PROJECT> is uppercase, e.g. INARIZ_DATA_ROOT.
    """
    project_root_override = os.getenv(f"{project.upper()}_DATA_ROOT")
    global_root_override = os.getenv("C_MARKET_DATA_ROOT")

    if project_root_override:
        return Path(project_root_override) / _strip_data_prefix(configured_dir)
    if global_root_override:
        return Path(global_root_override) / _strip_data_prefix(configured_dir)
    return configured_dir


def input_csv(project: str, data_type: str = None, filename: str = None, **kwargs):
    config = load_config()
    configured_dir = _normalize_config_dirpath(
        config[project]["data"][data_type]["dirpath"]
    )
    configured_dir = _resolve_data_dir(project, configured_dir)
    repo_root = Path(__file__).resolve().parent.parent

    if configured_dir.is_absolute():
        path = configured_dir / Path(filename)
    else:
        path = repo_root / configured_dir / Path(filename)
    if not path.exists():
        raise FileNotFoundError(path)

    if "skiprows" in config[project]["data"][data_type]:
        kwargs.setdefault("skiprows", config[project]["data"][data_type]["skiprows"])
    if "usecols" in config[project]["data"][data_type]:
        kwargs.setdefault("usecols", config[project]["data"][data_type]["usecols"])

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
            parsed = pd.to_datetime(
                df[col], errors="coerce", dayfirst=bool(format), format=format
            )
            if parsed.notna().mean() > 0.8:
                timestamp_col = col
                df[col] = parsed
                break
    else:
        df[timestamp_col] = pd.to_datetime(
            df[timestamp_col], errors="coerce", format=format
        )

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
            raise ValueError(
                f"source_timezone is required to localize timestamps. Not found in column '{timestamp_col}' nor provided as argument."
            )
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


def data_workflow(project: str, data_type: str, filename: str = None):
    df = input_csv(project, data_type, filename)

    config = load_config()

    # parse timestamp_col, and rename
    timestamp_col = config[project]["data"][data_type]["timestamp_col"]
    timestamp_format = config[project]["data"][data_type]["timestamp_format"]
    df[timestamp_col] = pd.to_datetime(
        df[timestamp_col], errors="coerce", format=timestamp_format
    )
    df = df.sort_values(timestamp_col)
    df = df.rename(columns={timestamp_col: "measured_at"})

    # convert to UTC, and rename
    source_timezone = config[project]["data"][data_type]["timezone"]
    df = localize_and_convert_to_utc(df, source_timezone)

    # give information on the frequency of the index:
    if "frequency" in config[project]["data"][data_type]:
        df = df.asfreq(config[project]["data"][data_type]["frequency"])

    return df
