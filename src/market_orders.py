from __future__ import annotations

import datetime
from pathlib import Path

import pandas as pd

from src.ingest import data_workflow

from src.utils import load_config, convert_m3_to_mwhth
from src.predict import copy_median_values
from src.dataset import resample

ORDER_HEADER = [
    "asset_id",
    "Delivery_datetime(UTC_start_of_period)",
    "Price_min(E_MWh)",
    "Price_max(E_MWh)",
    "Power_in_kW(Sell)",
]


def build_market_orders(
    project_name: str,
    forecast: pd.DataFrame,
    prix_seuil_euro_mwh: float,
    puissance_chaudiere_elec_mw: float,
    capacite_min_gaz_mwhth: float,
    *,
    timestamp_col :str = "measured_at_utc",
    value_col: str, # must be in MWhth
    output_dir: Path | str = Path(r"data\market_orders"),
    run_at: datetime | pd.Timestamp | None = None,
    sep: str = ";",
) -> list[Path]:
    """
    Construit et écrit les fichiers CSV d'ordres de marché, un par jour.
    L'input et le résultat est en UTC.
    """

    df = forecast[[timestamp_col, value_col]].copy()

    if df[timestamp_col].dt.tz != datetime.timezone.utc:
        raise ValueError(f"Missing or wrong tzinfo for timestamp column {timestamp_col}")

    if df[timestamp_col].isna().any() | df[value_col].isna().any() :
        raise ValueError(f"NaN values in timestamp or value columns")

    # # read config info
    # config = load_config()
    # prix_seuil_euro_mwh = config[project_name]['prix_seuil_euro_mwh"]
    # puissance_chaudiere_elec_mw = config[project_name]["puissance_chaudiere_elec_mw"]
    # capacite_min_gaz_mwhth = config[project_name]["capacite_min_gaz_mwhth"]
    
    # prise en compte du seuil pour la chaudière gaz
    available_mwh = (df[value_col] - float(capacite_min_gaz_mwhth)).clip(lower=0)
    # conversion au quart d'heure
    available_power_mw = available_mwh * 60/15
    # prise en compte de la puissance max pour la chaudière élec
    available_power_mw = available_power_mw.clip(upper=float(puissance_chaudiere_elec_mw))
    # valeur finale
    power_kw_sell = -1 * (available_power_mw * 1000)

    orders = pd.DataFrame({
        "asset_id": project_name,
        "Delivery_datetime(UTC_start_of_period)": df[timestamp_col].dt.strftime("%Y-%m-%d %H:%M:%S"),
        "Price_min(E_MWh)": -500.0,
        "Price_max(E_MWh)": float(prix_seuil_euro_mwh),
        "Power_in_kW(Sell)": power_kw_sell,
        })

    run_at = pd.Timestamp(run_at or datetime.datetime.now())
    run_day = run_at.strftime("%Y%m%d")
    run_time = run_at.strftime("%H%M")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    orders["_day"] = df[timestamp_col].dt.strftime("%Y%m%d")
    output_paths: list[Path] = []
    for day, group in orders.groupby("_day", sort=True):
        filename = f"{project_name}_{day}_{run_day}_{run_time}.csv"
        output_path = output_dir / filename
        group[ORDER_HEADER].to_csv(output_path, sep=sep, index=False)
        output_paths.append(output_path)

    return output_paths


def complex_market_orders_data_workflow(project: str):
    df = data_workflow(project)

    # include the unit into the main column name
    df = df.rename(columns={"Valeur": "steam_production_(m3/h)"})

    # for other columns, keep only numerical columns
    # set the timestamp as a column with a standard name, not as the index
    df = df.drop(columns=["Unité"])

    df = df[["measured_at_utc", "steam_production_(m3/h)"]] #required, as the data_workflow creates new columns when localizing and converting to utc
    df_15min = resample(df, desired_timedelta="15min", aggregate_function="mean")
    df_15min["steam_production_(m3/h)"] = df_15min["steam_production_(m3/h)"].fillna(0)
    df_median1week = copy_median_values(df_15min, "measured_at_utc", "steam_production_(m3/h)", respect_holidays=False, respect_weekdays=True, respect_time=True, extension="semaine")
    config = load_config()

    df_median1week = convert_m3_to_mwhth(
        df_median1week,
        "steam_production_(m3/h)",
        converted_value_col = "steam_production_mwhth"
    )

    paths = build_market_orders(
        project_name=project,
        forecast=df_median1week,  # output de simple_copy / copy_median_values
        prix_seuil_euro_mwh=config[project]["prix_seuil_euro_mwh"][0],
        puissance_chaudiere_elec_mw=config[project]["puissance_chaudiere_elec_mw"],
        capacite_min_gaz_mwhth=config[project]["capacite_min_gaz_mwhth"],
        # timestamp_col="measured_at_utc",  # optionnel si non détectable
        value_col="steam_production_mwhth",  # optionnel si non détectable
    )
    return paths