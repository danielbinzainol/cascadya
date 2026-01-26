from pathlib import Path
import pandas as pd
#
from utils import load_config

        
def input_csv(project: str):
    config = load_config() 
    path = Path(config[project]["data"]["path"])
    if not path.exists():
        raise FileNotFoundError(path)

    df = pd.read_csv(path, sep=";", decimal=",")

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
    y = df.select_dtypes(include="number")

    if y.empty:
        raise ValueError("No numeric columns found to plot.")
        
    return y

def data_workflow(project: str):
    df = input_csv(project)
    y = parse_date_col(df)

    config = load_config() 
    y = y.asfreq(config[project]["data"]["frequency"])
    
    return y