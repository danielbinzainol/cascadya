from pathlib import Path
import pandas as pd

INPUT_DIR = Path(
    r"D:\Cascadya\Cascadya - Documents\08. COMPTE CLIENT\Inariz_Lamballe\2. Données sous NDA\planning de production\Planning week 07 V0 LAM (PLANNING).xlsm"
)

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
    # missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    # if missing:
    #     missing_str = ", ".join(missing)
    #     raise ValueError(f"Missing columns in {path.name}: {missing_str}")

    # df = df[REQUIRED_COLUMNS].dropna(how="all")

    # df["Désignation caractéristique"] = (
    #     df["Désignation caractéristique"].astype(str).str.strip()
    # )
    # df = df[df["Désignation caractéristique"] == "conso gaz chaudiere SV4"]

    # df["Valeur mesurée"] = _coerce_numeric(df["Valeur mesurée"])
    # df["Valeur mesurée le"] = pd.to_datetime(
    #     df["Valeur mesurée le"],
    #     errors="coerce",
    #     dayfirst=True,
    # )
    # df = df.dropna(subset=["Valeur mesurée le"])

    return df


if __name__ == "__main__":
    df = _read_inariz_planning_excel(INPUT_DIR)