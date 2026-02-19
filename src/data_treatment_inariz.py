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
    print(df)

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
        df_section = df_section.iloc[2:]
        # Drop the last row, if present, with the Total duration
        keep_mask = df_section[2].notna() & df_section[3].notna()
        df_section = df_section[keep_mask]
        #
        df_section = df_section.rename(columns=REQUIRED_COLUMNS_POSITIONS)
        df_section = df_section[REQUIRED_COLUMNS_POSITIONS.values()]
        df_sections.append(df_section)

    return df_sections


if __name__ == "__main__":
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

