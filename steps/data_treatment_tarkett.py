from __future__ import annotations

from pathlib import Path
import pandas as pd
from tqdm import tqdm
import datetime

from plots import plot_timeseries_csv, plot_gap_filled_timeseries

DEFAULT_INPUT_DIR = Path(
    r"D:\Cascadya\Cascadya - Documents\08. COMPTE CLIENT\Tarkett_Sedan\2. Données sous NDA\Données de Consommation gaz 2025"
)
DEFAULT_INTERIM_OUTPUT_PATH_NOT_SAMPLED = Path(r"data\tarkett\interim") / "data_tarkett_not_sampled.csv"
DEFAULT_INTERIM_OUTPUT_PATH = Path(r"data\tarkett\interim") / "data_tarkett.csv"

DEFAULT_OUTPUT_PATH = Path(r"data\tarkett\processed") / "data_tarkett_gap_filled.csv"

REQUIRED_COLUMNS = [
    "Désignation caractéristique",
    "Unité",
    "Valeur mesurée",
    "Valeur mesurée le",
]

COEFF_M3_NM3 = 1.2
COEFF_PCS_KWH_NM3 = 11.35

JOURS_OFF_PRESENTS = [datetime.date(2025, 5, 1), # férié
                      datetime.date(2025, 5, 29), # férié
                      datetime.date(2025, 5, 30), #pont
                      ]

CRENEAUX_3_8 = 4 # [4, 12, 20] # en vrai, plutôt à ces heures-là et demi, on suppose


# sur lesquels il manque de la donnée, en plus des dimanche
# il existe des jours fériés sur lesquels il ne manque pas de donnée, est déjà à 0
JOURS_OFF_MANQUANTS = [datetime.date(2025, 4, 21), # férié
                       datetime.date(2025, 5, 2), # pont
                       datetime.date(2025, 5, 3), # samedi pont, juste pour le tag
                       datetime.date(2025, 5, 31), # samedi pont, juste pour le tag
                       datetime.date(2025, 7, 14), # férié
                       datetime.date(2025, 7, 19), # je ne sais pas pourquoi
                       datetime.date(2025, 8, 15), # férié
                       datetime.date(2025, 8, 16), # pont
                       datetime.date(2025, 11, 10), #pont
                       datetime.date(2025, 11, 11), # férié
                       datetime.date(2025, 12, 13), # je ne sais pas pourquoi
                       ]

# sur lesquels il manque de la donnée.
JOURS_END_MANQUANTS = [datetime.date(2025, 7, 18), # je ne sais pas pourquoi
                       datetime.date(2025, 8, 14), # veille de férié complet
                       datetime.date(2025, 11, 1), # férié
                       datetime.date(2025, 12, 12), # je ne sais pas pourquoi
                       ]

JOURS_BACK_MANQUANTS = [datetime.date(2025, 1, 6), # lendemain de vacances
                        datetime.date(2025, 4, 22), # lendemain de férié
                        datetime.date(2025, 7, 15), # lendemain de férié
                        datetime.date(2025, 11, 12), # lendemain de férié
                        ]



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


def find_duplicate_timestamps_with_same_value(
    duplicates_df: pd.DataFrame,
    timestamp_col: str = "Valeur mesurée le",
    value_col: str = "Valeur mesurée",
) -> list[pd.Timestamp]:
    if duplicates_df.empty:
        return []
    nunique_by_timestamp = duplicates_df.groupby(timestamp_col)[value_col].nunique(
        dropna=False
    )
    return list(nunique_by_timestamp[nunique_by_timestamp == 1].index)


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
    return hourly #todo remplir début et fin d'année

def tag_activity(
        df: pd.DataFrame, 
        timestamp_col: str = "Valeur mesurée le",
) -> pd.DataFrame:
    # utils
    df[timestamp_col] = pd.to_datetime(df[timestamp_col], errors="coerce")
    df = df.sort_values(timestamp_col).reset_index(drop=True)

    df["_date"] = df[timestamp_col].dt.date
    
    unique_dates = [d for d in df["_date"].dropna().unique()]

    missing_off_days = set(JOURS_OFF_MANQUANTS)
    present_off_days = set(JOURS_OFF_PRESENTS)
    missing_end_of_work_days = set(JOURS_END_MANQUANTS)
    missing_back_to_work_days = set(JOURS_BACK_MANQUANTS)

    # back_to_work
    back_to_work_mondays = {
        d
        for d in unique_dates
        if d not in missing_off_days
        and d not in missing_end_of_work_days
        and d.weekday() == 0
    }

    all_back_to_work_days = missing_back_to_work_days.union(back_to_work_mondays)

    # off
    sundays = {
        d
        for d in unique_dates
        if d.weekday() == 6
    }

    non_sunday_off_days = missing_off_days.union(present_off_days)
    all_off_days = non_sunday_off_days.union(sundays)

    # end_of_work
    end_of_work_saturdays = {
        d
        for d in unique_dates
        if d not in missing_off_days
        and d not in missing_back_to_work_days
        and d.weekday() == 5
    }

    all_end_of_work_days = missing_end_of_work_days.union(end_of_work_saturdays)

    # perform tag
    df["activity"] = "active"

    back_to_work_mask = df["_date"].isin(all_back_to_work_days)
    df.loc[back_to_work_mask, "activity"] = "back_to_work"

    off_mask = df["_date"].isin(all_off_days)
    df.loc[off_mask, "activity"] = "off"

    end_of_work_mask = df["_date"].isin(all_end_of_work_days)
    df.loc[end_of_work_mask, "activity"] = "end_of_work"

    return df, non_sunday_off_days, all_back_to_work_days

def gap_fill_hourly_timeseries(
    df_hourly: pd.DataFrame,
    non_sunday_off_days,
    all_back_to_work_days,
    timestamp_col: str = "Valeur mesurée le",
    value_col: str = "MWh use",
) -> pd.DataFrame:
    # utils
    df = df_hourly.copy()
    df[timestamp_col] = pd.to_datetime(df[timestamp_col], errors="coerce")
    df = df.sort_values(timestamp_col).reset_index(drop=True)

    df["_hour"] = df[timestamp_col].dt.hour
    df["_weekday"] = df[timestamp_col].dt.weekday
    df["_date"] = df[timestamp_col].dt.date    


    # off_days = set(JOURS_FERIES_ET_PONTS)
    # df["_is_off_day"] = df["_date"].isin(off_days)
    # unique_dates = [d for d in df["_date"].dropna().unique()]

    # def _previous_workday(day: datetime.date) -> datetime.date:
    #     prev = day - datetime.timedelta(days=1)
    #     while prev.weekday() >= 5:
    #         prev -= datetime.timedelta(days=1)
    #     return prev

    # back_to_work_days = {
    #     d
    #     for d in unique_dates
    #     if d not in off_days
    #     and d.weekday() < 5
    #     and _previous_workday(d) in off_days
    # }
    # end_of_work_off_days = {
    #     d
    #     for d in unique_dates
    #     if d in off_days
    #     and (d - datetime.timedelta(days=1)) not in off_days
    #     and (d - datetime.timedelta(days=1)).weekday() < 5
    # }

    # if isinstance(CRENEAUX_3_8, (list, tuple, set)):
    #     end_of_work_hour_mask = df["_hour"].isin(CRENEAUX_3_8)
    # else:
    #     end_of_work_hour_mask = df["_hour"] <= CRENEAUX_3_8

    # stats: remove NaNs and days taggued as OFF from stats
    ##todo can be deleted because same as below but better below?
    missing_mask = df[value_col].isna()
    original_mask = ~missing_mask
        
    df.loc[original_mask, "tag"] = "original"

    ##
    stats_mask = original_mask & ~df["_date"].isin(non_sunday_off_days)

    # stats_mask = original_mask & ~(df["_is_off_day"] & (df[value_col] == 0))
    stats = df.loc[stats_mask].groupby(["_weekday", "_hour"])[value_col]
    weekday_hour_median = stats.median()
    weekday_hour_q1 = stats.quantile(0.25)

    def _median_for_idx(row_idx: int) -> float:
        hour = df.at[row_idx, "_hour"]
        date = df.at[row_idx, "_date"]
        # is_end_hour = end_of_work_hour_mask.iat[row_idx]
        if date in all_back_to_work_days:
            source_weekday = 0
        else:
            source_weekday = df.at[row_idx, "_weekday"]
        return weekday_hour_median.get((source_weekday, hour))

    # Fill gaps from the end, 
    # if weekday: validating against the target hour's weekday Q1
    # if back_to_work day: validating against the target hour's back_to_work monday Q1
    if missing_mask.any():
        missing_mask_arr = missing_mask.to_numpy()
        original_mask_arr = original_mask.to_numpy()
        n_rows = len(df)
        i = 0

        # Scan the full series for the next contiguous missing block (can span days).
        while i < n_rows:
            if not missing_mask_arr[i]:
                i += 1
                continue
            start = i
            while i < n_rows and missing_mask_arr[i]:
                i += 1
            end = i - 1

            target_idx = i
            target_hour = df.at[target_idx, "_hour"]
            target_weekday = df.at[target_idx, "_weekday"]
            q1_target = weekday_hour_q1.get((target_weekday, target_hour))
            current_value_of_target = df.at[target_idx, value_col]

            modified = False

            # Walk backward through the block, validating against the target value.
            k = end
            while k >= start:
                median_val_for_gap = _median_for_idx(k)
                # If stats/target are missing, fill the rest with zeros and stop.
                if pd.isna(median_val_for_gap) or pd.isna(current_value_of_target):
                    for m in range(k, start - 1, -1):
                        df.at[m, value_col] = 0
                        df.at[m, "tag"] = "gap-filled with zeros because the stats info is missing"
                    if not modified:
                        df.at[target_idx, "tag"] = "considered, not modified, because the stats info is missing"
                    break

                # check median_val_for_gap against its impact on target compared to q1
                candidate_for_target = current_value_of_target - median_val_for_gap
                if not pd.isna(q1_target):
                    threshold_ok = candidate_for_target > q1_target
                else:
                    raise ValueError(f"Missing Q1 info for target. weekday_hour_q1: {weekday_hour_q1}, target_weekday: {target_weekday}, target_hour: {target_hour}")

                # If the gap-filled value is zero, gap-fill all previous points with a 0
                if median_val_for_gap == 0.0:
                    for m in range(k, start - 1, -1):
                        df.at[m, value_col] = 0
                        df.at[m, "tag"] = "gap-filled with 0 because later points already filled at 0"
                    break

                # If the test is valid, accept this fill and update the target value for the next step.
                if threshold_ok:
                    df.at[k, value_col] = median_val_for_gap
                    df.at[k, "tag"] = "gap-filled implying modification"
                    current_value_of_target = candidate_for_target
                    modified = True
                    k -= 1
                    continue # passe au prochain tour de boucle

                # If the test is invalid, fill the rest of the beginning of the block; fill with zeros, break the while loop
                for m in range(k, start - 1, -1):
                    df.at[m, value_col] = 0
                    df.at[m, "tag"] = "gap-filled rest of block because threshold of modification already reached"
                break

            # Commit the final modified target value
            if modified:
                df.at[target_idx, value_col] = current_value_of_target
                df.at[target_idx, "tag"] = "modified"
            # if no test has been seen as valid, the target has not been modified   
            else:
                df.at[target_idx, "tag"] = "considered, not modified"

    # Create index for missing dates for Christmas holidays, and fill with zeros all remaining missing values
    df = df.set_index("Valeur mesurée le")
    date_index2 = pd.date_range(start="2025-01-01 00:00:00", end="2025-12-31 23:00:00", freq="h")
    df = df.reindex(date_index2)
    df = df.reset_index(names="Valeur mesurée le")
    
    holidays_mask = df["tag"].isna()
    df.loc[holidays_mask, "activity"] = "holidays"
    df.loc[holidays_mask, "tag"] = "gap-filled with zero for holidays"
    df.loc[holidays_mask, value_col] = 0

    return df.drop(columns=["_hour", "_weekday", "_date"]) #, "_is_off_day"


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


def detect_elapsed_time_anomalies(
    df: pd.DataFrame,
    timestamp_col: str = "Valeur mesurée le",
) -> tuple[pd.DataFrame, pd.Timedelta]:
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
    anomalies = df.loc[anomalies_mask, [timestamp_col]].copy()
    anomalies["Previous timestamp"] = df[timestamp_col].shift(1)
    anomalies["Elapsed"] = elapsed[anomalies_mask]
    anomalies["Expected elapsed"] = expected_delta

    return anomalies, expected_delta


def build_tarkett_dataset(
    input_dir: Path | str = DEFAULT_INPUT_DIR,
    output_interim_path_not_sampled: Path | str = DEFAULT_INTERIM_OUTPUT_PATH_NOT_SAMPLED,
    output_interim_path: Path | str = DEFAULT_INTERIM_OUTPUT_PATH,
    output_path: Path | str = DEFAULT_OUTPUT_PATH,
    sep: str = ";",
    decimal: str = ",",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:

    output_interim_path_not_sampled = Path(output_interim_path_not_sampled)
    output_interim_path_not_sampled.parent.mkdir(parents=True, exist_ok=True)

    if output_interim_path_not_sampled.exists():
        print("---------------- loading existing interim files (cache) ------------")
        df = pd.read_csv(output_interim_path_not_sampled, sep=sep, decimal=decimal)
        if "Valeur mesurée le" in df.columns:
            df["Valeur mesurée le"] = pd.to_datetime(
                df["Valeur mesurée le"],
                errors="coerce",
                yearfirst=True,
                format="ISO8601"
            )
    else:
        # contient les timestamps duplicates et les timestamps manquants
        df = load_tarkett_files(input_dir)
        df = df.sort_values("Valeur mesurée le")
        df.to_csv(output_interim_path_not_sampled, index=False, sep=sep, decimal=decimal)

    print("---------------- loading files completed ------------")
    
    duplicates = detect_duplicate_timestamps(df)
    duplicate_timestamps_that_can_be_removed = (
        find_duplicate_timestamps_with_same_value(duplicates)
    )

    elapsed_anomalies, expected_delta = detect_elapsed_time_anomalies(df)
    print(
        "---------------- elapsed anomalies : "
        f"{len(elapsed_anomalies)} (expected {expected_delta}) ------------"
    )

    if duplicate_timestamps_that_can_be_removed:
        removable_mask = (
            df["Valeur mesurée le"].isin(duplicate_timestamps_that_can_be_removed)
            & df.duplicated(subset=["Valeur mesurée le"], keep="first")
        )
        df = df.loc[~removable_mask]

    df = add_mwh_measure(df)
    df = add_mwh_use(df)

    df_hourly = aggregate_hourly(df)
    df_hourly = df_hourly[["Valeur mesurée le", "MWh use"]]

    output_interim_path = Path(output_interim_path)
    output_interim_path.parent.mkdir(parents=True, exist_ok=True)
    df_hourly.to_csv(output_interim_path, index=False, sep=sep, decimal=decimal)

    # gap-filling
    df_hourly, non_sunday_off_days, all_back_to_work_days = tag_activity(df_hourly)
    df_hourly_gap_filled = gap_fill_hourly_timeseries(df_hourly, non_sunday_off_days, all_back_to_work_days)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)    
    df_hourly_gap_filled.to_csv(output_path, index=False, sep=sep, decimal=decimal)

    plot_timeseries_csv(df_hourly.set_index("Valeur mesurée le"))
    plot_gap_filled_timeseries(df_hourly_gap_filled)

    return df_hourly, df_hourly_gap_filled, duplicates, elapsed_anomalies


if __name__ == "__main__":
    df_hourly, df_hourly_gap_filled, duplicates, elapsed_anomalies = build_tarkett_dataset()
