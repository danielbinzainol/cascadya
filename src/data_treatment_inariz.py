from pathlib import Path
import time
import pandas as pd

INPUT_DIR = Path(
    r"D:\Cascadya\Cascadya - Documents\08. COMPTE CLIENT\Inariz_Lamballe\2. Données sous NDA\planning de production"
)

REQUIRED_COLUMNS_POSITIONS = {2: "DATE", 4: "CODE PF10/SF90", 12:"temps de production", 14:"temps nettoyage"}

DEFAULT_INTERMEDIARY_OUTPUT_DIR = Path(r"data\inariz\intermediary")


def detect_most_recent_file(input_dir: Path):
    mtime_path = {
        path.stat().st_mtime: path #time of last modification of the file, expressed in epoch (seconds from Jan 1st 1970 UTC)
        for path in input_dir.iterdir()
        if path.is_file() and path.suffix.lower().startswith(".xls")
    }
    most_recent_modification_date = sorted(mtime_path.keys())[-1]
    most_recent_file_path = mtime_path[most_recent_modification_date]
    return most_recent_modification_date, most_recent_file_path

def _read_inariz_planning_excel(path: Path) -> pd.DataFrame:
    # print(f"---------------- Start reading {path} ------------")

    while True:
        try:
            df = pd.read_excel(path, sheet_name="PlanningV2", header=None)
            break
        except PermissionError:
            input(
                f"PermissionError: {path} is open elsewhere. "
                "Please close it, then press Enter to retry."
            )

    df = df.drop(columns=[0, 1], errors="ignore")

    def _is_empty_cell(value) -> bool:
        if pd.isna(value):
            return True
        if isinstance(value, str) and value.strip() == "":
            return True
        return False

    col_2 = df[2]
    df = df[~col_2.apply(_is_empty_cell)].reset_index(drop=True)

    def _is_split_row(value) -> bool:
        if not isinstance(value, str):
            return False
        cleaned = value.strip()
        return cleaned not in {"DATE", "Total"} and cleaned != ""

    # Identify rows for which the date column is empty
    split_positions = [
        idx for idx, value in enumerate(df[2]) if _is_split_row(value)
    ]
    
    df_sections = []
    for i, start in enumerate(split_positions):
        end = split_positions[i + 1] if i + 1 < len(split_positions) else len(df)
        # Drop the identified rows for which the date column is empty
        df_section = df.iloc[start:end].reset_index(drop=True)
        # Drop the first two rows, headers
        df_section = df_section.iloc[2:].reset_index(drop=True)
        # Drop the last row, if present, with the Total duration
        keep_mask = df_section[2].notna() & df_section[3].notna()
        df_section = df_section[keep_mask]
        # Rename columns and keep only the relevant ones
        df_section = df_section.rename(columns=REQUIRED_COLUMNS_POSITIONS)
        df_section = df_section[REQUIRED_COLUMNS_POSITIONS.values()]

        # Drop the rows overritten by a lower row, for which the date is later than a lower row with an earlier date
        # Rule : if the date goes in the past, discard the whole data for the inital day. 
        # Because it is possible that 3 rows starting 5am, 11am, 4pm are replaced by one unique row starting 6am.

        # todo convert utc avant ça ??
        df_section["_date"] = pd.to_datetime(df_section["DATE"]).dt.date
        df_section["_elapsed"] =  pd.to_datetime(df_section["DATE"]).diff() #periods=-1 would give difference with following row
        # detect if one day has a negative elapsed time, thus "erased" rows
        # if there is a negative elapsed time
        if df_section["_elapsed"].le(pd.Timedelta(0)).any():
            # initialise the _to_delete column, necessary in case several situations to_delete are present
            df_section["_to_delete"] = ""
            # then loop through all rows individually to find it
            for idx, value in enumerate(df_section["_elapsed"]):
                if value < pd.Timedelta(0):
                    # select all elements from previous rows that have the same date or later, and have not yet been taggued "to_delete"
                    to_delete_mask = (df_section.loc[:idx-1,"_date"] >= df_section.at[idx,"_date"]) & (df_section["_to_delete"] != "to_delete")
                    df_section.loc[to_delete_mask, "_to_delete"] = "to_delete"

            erased_mask = df_section["_to_delete"] == "to_delete"

            # Remove the "erased" rows
            df_section = df_section[~erased_mask]
            
        # keep only the relevant columns
        df_section = df_section[REQUIRED_COLUMNS_POSITIONS.values()]

        #
        df_sections.append(df_section)

    return df_sections

def ingest_prod_planning_inariz():
    # todo ajouter ici une boucle while à un moment
    last_modified_date = 0
    most_recent_modification_date, most_recent_file_path = detect_most_recent_file(INPUT_DIR)
    if most_recent_modification_date < last_modified_date:
        raise ValueError("dates pas cohérentes")
    elif most_recent_modification_date == last_modified_date:
        # print(f"No new modification since {time.localtime(most_recent_modification_date)}")
        pass
    elif most_recent_modification_date > last_modified_date:
        last_modified_date = most_recent_modification_date
        # print(f"New modification detected on {time.localtime(most_recent_modification_date)}, new file parsed.")

        df_sections = _read_inariz_planning_excel(most_recent_file_path)
        for i, df_section in enumerate(df_sections):
            output_filename = most_recent_file_path.stem + f"_autoclave_{i+1}_inariz.csv"
            output_path = DEFAULT_INTERMEDIARY_OUTPUT_DIR / output_filename

            DEFAULT_INTERMEDIARY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            df_section.to_csv(output_path, index=False, sep=";", decimal=",")
        
    return None


def check_planning_sequence(
    csv_path: Path | str,
    *,
    base_dir: Path = DEFAULT_INTERMEDIARY_OUTPUT_DIR,
    sep: str = ";",
    date_col: str = "DATE",
    prod_col: str = "temps de production",
    clean_col: str = "temps nettoyage",
) -> pd.DataFrame:
    """
    Read a planning CSV and check that:
    DATE[n] + temps de production[n] + temps nettoyage[n] == DATE[n+1].

    Returns a DataFrame listing mismatches (empty if all good).
    """
    path = Path(csv_path)
    if not path.is_file():
        path = base_dir / path
    if not path.exists():
        raise FileNotFoundError(path)

    df = pd.read_csv(path, sep=sep)
    missing_cols = [col for col in (date_col, prod_col, clean_col) if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing columns in {path.name}: {', '.join(missing_cols)}")

    df = df[[date_col, prod_col, clean_col]].copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df[prod_col] = pd.to_timedelta(df[prod_col], errors="coerce")
    df[clean_col] = pd.to_timedelta(df[clean_col], errors="coerce")

    total_duration = df[prod_col] + df[clean_col]
    expected_next = df[date_col] + total_duration
    actual_next = df[date_col].shift(-1)

    mismatch_mask = expected_next.notna() & actual_next.notna() & (expected_next != actual_next)
    mismatches = df.loc[mismatch_mask].copy()
    mismatches["expected_next_DATE"] = expected_next[mismatch_mask]
    mismatches["actual_next_DATE"] = actual_next[mismatch_mask]

    mismatches = mismatches.reset_index(drop=True)

    if mismatches.empty:
        return None, None
    else:
        print(csv_path)
        print(mismatches)
        return csv_path, mismatches

def check_all_planning_sequence(
    dir: Path | str,
):
    input_dir = Path(dir)
    if not input_dir.is_dir():
       raise ValueError(f"wrong directory path: {input_dir}")  
    if not input_dir.exists():
        raise FileNotFoundError(input_dir)
    
    for path in input_dir.iterdir():
        csv_path, mismatches = check_planning_sequence(path)

    return None


if __name__ == "__main__":
    # mismatches = check_planning_sequence("Planning week 07 V9 LAM (PLANNING)_autoclave_1_inariz.csv")
    # print(mismatches)
    check_all_planning_sequence(r"data\inariz\intermediary")
