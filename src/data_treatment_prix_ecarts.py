from __future__ import annotations

from pathlib import Path

import pandas as pd

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 180)

DATA_DIR = Path(
    r"D:\\Cascadya\\Cascadya - Documents\\10. IT\\5. Script Faisa\\Equilibrage 2025"
)
FILE_PATTERN = "*MMA_HECAR_2025*.csv"

## 1) Chargement et fusion des 12 fichiers

### Remarque: la premiere ligne de chaque fichier est un titre texte (a ignorer).


def read_month_file(path: Path) -> pd.DataFrame:
    """Read one monthly CSV, skipping the first title row."""
    last_error = None
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            df = pd.read_csv(path, sep=";", skiprows=1, encoding=encoding)
            break
        except UnicodeDecodeError as exc:
            last_error = exc
    else:
        raise last_error

    df.columns = [str(c).strip() for c in df.columns]

    ts_cols = df.columns[:2]
    for col in ts_cols:
        df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")

    # Add provenance for traceability.
    df["source_file"] = path.name
    return df


def build_df_all():
    csv_files = sorted(DATA_DIR.glob(FILE_PATTERN))
    assert len(csv_files) == 12, f"Expected 12 files, found {len(csv_files)}"

    frames = []
    file_index = []
    for path in csv_files:
        month_df = read_month_file(path)

        first_ts = month_df.iloc[0, 0]
        month_key = first_ts.to_period("M") if pd.notna(first_ts) else pd.NaT

        file_index.append(
            {
                "file": path.name,
                "rows": len(month_df),
                "first_timestamp": first_ts,
                "month_from_data": str(month_key),
            }
        )
        frames.append((month_key, month_df))

    # Sort by month inferred from timestamps (more reliable than filename order).
    frames_sorted = [df for _, df in sorted(frames, key=lambda x: x[0])]
    df_all = pd.concat(frames_sorted, ignore_index=True)
    # do not sort again using.sort_values(by=frames_sorted[0].columns[0]).reset_index(drop=True)
    # we need all rows in order, especially the ones switching to/from DST.
    # for an easier transformation into UTC.

    file_index_df = (
        pd.DataFrame(file_index).sort_values("first_timestamp").reset_index(drop=True)
    )
    display(file_index_df)

    return df_all

    # Attention les données sont en "Europe/Paris" à la sortie, il y a un jour avec 25heures et un jour avec 23heures
