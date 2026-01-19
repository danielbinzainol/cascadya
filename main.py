from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

def input_csv(
    csv_path: str = r"D:\Cascadya\Cascadya - Documents\8. COMPTE CLIENT\__Dossier Simulation MBC\France champignon\données_bonduelle.csv",
):
    path = Path(csv_path)
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

def plot_timeseries_csv(
    y: pd.DataFrame,
):
    ax = y.plot(figsize=(10, 6))

    ax.set_ylabel("Value")
    # ax.set_title(path.name)
    ax.legend(loc="best")
    plt.tight_layout()
    plt.show()


def plot_weekday_seasonal_csv(
        y: pd.DataFrame,
):
    weekday_means = y.groupby(y.index.dayofweek).mean().reindex(range(7))
    ax = weekday_means.plot(figsize=(10, 6))
    ax.set_xlabel("Weekday")
    ax.set_ylabel("Mean value")
    # ax.set_title(f"{path.name} (Weekday seasonal plot)")
    ax.set_xticks(range(7))
    ax.set_xticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    ax.legend(loc="best")
    plt.tight_layout()
    plt.show()

def data_workflow():
    df = input_csv()
    y = parse_date_col(df)
    return y

def plot_workflow(y):
    plot_timeseries_csv(y)
    plot_weekday_seasonal_csv(y)

if __name__ == "__main__":
    y = data_workflow()
    plot_workflow(y)