from __future__ import annotations

from pathlib import Path
import pandas as pd
from tqdm import tqdm

DEFAULT_INPUT_DIR = Path(
    r"D:\Cascadya\Cascadya - Documents\08. COMPTE CLIENT\Tarkett_Sedan\2. Données sous NDA\Données de Consommation gaz 2025"
)
DEFAULT_INTERIM_OUTPUT_PATH = Path("data\tarkett\interim") / "data_tarkett_not_sampled.csv"

DEFAULT_OUTPUT_PATH = Path("data\tarkett\processed") / "data_tarkett.csv"

REQUIRED_COLUMNS = [
    "Désignation caractéristique",
    "Unité",
    "Valeur mesurée",
    "Valeur mesurée le",
]

COEFF_M3_NM3 = 1.2
COEFF_PCS_KWH_NM3 = 11.35


def _coerce_numeric(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return series
    cleaned = series.astype(str).str.replace(",", ".", regex=False)
    return pd.to_numeric(cleaned, errors="coerce")


def _read_tarkett_excel(path: Path) -> pd.DataFrame:
    # print(f"---------------- Start reading {path} ------------")

    while True:
        try:
            df = pd.read_excel(path, header=1)
            break
        except PermissionError:
            input(
                f"PermissionError: {path} is open elsewhere. "
                "Please close it, then press Enter to retry."
            )
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        missing_str = ", ".join(missing)
        raise ValueError(f"Missing columns in {path.name}: {missing_str}")

    df = df[REQUIRED_COLUMNS].dropna(how="all")

    df["Désignation caractéristique"] = (
        df["Désignation caractéristique"].astype(str).str.strip()
    )
    df = df[df["Désignation caractéristique"] == "conso gaz chaudiere SV4"]

    df["Valeur mesurée"] = _coerce_numeric(df["Valeur mesurée"])
    df["Valeur mesurée le"] = pd.to_datetime(
        df["Valeur mesurée le"],
        errors="coerce",
        dayfirst=True,
    )
    df = df.dropna(subset=["Valeur mesurée le"])

    return df


def load_tarkett_files(input_dir: Path | str = DEFAULT_INPUT_DIR) -> pd.DataFrame:
    input_path = Path(input_dir)
    if not input_path.exists():
        raise FileNotFoundError(input_path)

    print("---------------- Start loading ------------")

    files = sorted(
        path
        for path in input_path.iterdir()
        if path.is_file() and path.suffix.lower().startswith(".xls")
    )
    if not files:
        raise FileNotFoundError(f"No Excel files found in {input_path}")

    frames = []
    for path in tqdm(files, desc="Reading Excel files", unit="file"):
        frames.append(_read_tarkett_excel(path))
    return pd.concat(frames, ignore_index=True)


def detect_duplicate_timestamps(
    df: pd.DataFrame,
    timestamp_col: str = "Valeur mesurée le",
) -> pd.DataFrame:
    duplicates = df[timestamp_col].duplicated(keep=False)
    return df.loc[duplicates].sort_values(timestamp_col)


def add_mwh_measure(
    df: pd.DataFrame,
    coeff_m3_nm3: float = COEFF_M3_NM3,
    coeff_pcs_kwh_nm3: float = COEFF_PCS_KWH_NM3,
    value_col: str = "Valeur mesurée",
) -> pd.DataFrame:
    df = df.copy()
    df["MWh mesure"] = df[value_col] * coeff_m3_nm3 * coeff_pcs_kwh_nm3 / 1000
    return df


def add_mwh_use(
    df: pd.DataFrame,
    timestamp_col: str = "Valeur mesurée le",
    value_col: str = "MWh mesure",
    diff_col: str = "MWh use",
) -> pd.DataFrame:
    df = df.sort_values(timestamp_col).copy()
    df[diff_col] = df[value_col].diff()
    return df


def aggregate_hourly(
    df: pd.DataFrame,
    timestamp_col: str = "Valeur mesurée le",
    value_col: str = "MWh use",
) -> pd.DataFrame:
    df = df.sort_values(timestamp_col)
    hourly = (
        df.set_index(timestamp_col)[value_col]
        .resample("h")
        .sum(min_count=1)
        .reset_index()
    )
    return hourly


def find_missing_timestamps_full_year(
    df: pd.DataFrame,
    year: int,
    timestamp_col: str = "Valeur mesurée le",
    freq: str = "h",
) -> pd.DataFrame:
    freq_norm = freq.lower()
    if freq_norm in {"h", "hour", "hourly"}:
        start = pd.Timestamp(year=year, month=1, day=1, hour=0)
        end = pd.Timestamp(year=year, month=12, day=31, hour=23)
        align = "h"
    elif freq_norm in {"d", "day", "daily"}:
        start = pd.Timestamp(year=year, month=1, day=1)
        end = pd.Timestamp(year=year, month=12, day=31)
        align = "d"
    else:
        start = pd.Timestamp(year=year, month=1, day=1)
        end = pd.Timestamp(year=year, month=12, day=31)
        align = freq

    expected = pd.date_range(start, end, freq=freq)
    actual = (
        pd.to_datetime(df[timestamp_col], errors="coerce", dayfirst=True)
        .dropna()
        .dt.floor(align)
    )
    missing = expected.difference(pd.DatetimeIndex(actual.unique()))
    return pd.DataFrame({timestamp_col: missing})


def build_tarkett_dataset(
    input_dir: Path | str = DEFAULT_INPUT_DIR,
    output_interim_path: Path | str = DEFAULT_INTERIM_OUTPUT_PATH,
    output_path: Path | str = DEFAULT_OUTPUT_PATH,
    sep: str = ";",
    decimal: str = ",",
    missing_year: int = 2025,
    missing_freq: str = "h",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    
    df = load_tarkett_files(input_dir)
    print("---------------- loading files completed ------------")
    df = df.sort_values("Valeur mesurée le")

    df.to_csv(output_interim_path, index=False, sep=sep, decimal=decimal)

    duplicates = detect_duplicate_timestamps(df)
    missing_timestamps = find_missing_timestamps_full_year(
        df,
        year=missing_year,
        freq=missing_freq,
    )
    print(
        f"---------------- missing timestamps ({missing_year}) : {len(missing_timestamps)} ------------"
    )
    df = add_mwh_measure(df)
    df = add_mwh_use(df)

    df_hourly = aggregate_hourly(df)
    df_hourly = df_hourly[["Valeur mesurée le", "MWh use"]]

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_hourly.to_csv(output_path, index=False, sep=sep, decimal=decimal)

    return df_hourly, duplicates, missing_timestamps
