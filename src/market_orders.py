from __future__ import annotations

import datetime
from pathlib import Path

import pandas as pd

from src.ingest import data_workflow

from src.utils import load_config, convert_saturated_steam_units
from src.predict import copy_median_values
from src.dataset import resample

COEFF_ELEC_BOILER_EFFICIENCY = 1

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
    capacite_min_gaz_kwhth: float,
    *,
    timestamp_col :str = "measured_at_utc",
    value_col: str, # must be in kWhth
    output_dir: Path | str = Path(r"data\market_orders"),
    run_at: datetime.datetime | pd.Timestamp | None = None,
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
        raise ValueError("NaN values in timestamp or value columns")

    if "kwhth" not in value_col.split("_")[-1]:
        raise ValueError(f"Value col {value_col} is not in kWh")

    # # read config info
    # config = load_config()
    # prix_seuil_euro_mwh = config[project_name]['prix_seuil_euro_mwh"]
    # puissance_chaudiere_elec_mw = config[project_name]["puissance_chaudiere_elec_mw"]
    # capacite_min_gaz_kwhth = config[project_name]["capacite_min_gaz_kwhth"]
    
    # prise en compte du seuil pour la chaudière gaz
    available_kwhth = (df[value_col] - float(capacite_min_gaz_kwhth)).clip(lower=0)
    # prise en compte du rendement de la chaudière élec
    available_kwh = available_kwhth / COEFF_ELEC_BOILER_EFFICIENCY
    # conversion en puissance sur le quart d'heure
    available_power_kw = available_kwh * 60/15
    # prise en compte de la puissance max pour la chaudière élec
    available_power_kw = available_power_kw.clip(upper=float(puissance_chaudiere_elec_mw)*1000)
    # valeur finale
    power_kw_sell = -1 * available_power_kw

    orders = pd.DataFrame({
        "asset_id": project_name, #todo changer, l'asset_id est un INT chez e6
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


# tmp: certaines valeurs codées en dur sont spécifiques à inariz pour l'instant.
def complex_market_orders_data_workflow(project: str):
    df = data_workflow(project)

    # include the unit into the main column name
    df = df.rename(columns={"Valeur": "steam_production_m3_h"})

    # for other columns, keep only numerical columns
    # set the timestamp as a column with a standard name, not as the index
    df = df.drop(columns=["Unité"])

    df = df[["measured_at_utc", "steam_production_m3_h"]] #required, as the data_workflow creates new columns when localizing and converting to utc
    df_15min = resample(df, desired_timedelta="15min", aggregate_function="mean")
    df_15min["steam_production_m3_h"] = df_15min["steam_production_m3_h"].fillna(0)
    df_median1week = copy_median_values(df_15min, "measured_at_utc", "steam_production_m3_h", respect_holidays=False, respect_weekdays=True, respect_time=True, extension="semaine")
    config = load_config()

    # convert m3/h to m3
    df_median1week["steam_production_m3"] = df_median1week["steam_production_m3_h"] * 15/60 

    df_median1week = convert_saturated_steam_units(
        df_median1week,
        "steam_production_m3",
        "steam_production_kwhth",
        "m3",
        "kWh th"
    )

    paths = build_market_orders(
        project_name=project,
        forecast=df_median1week,  # output de simple_copy / copy_median_values
        prix_seuil_euro_mwh=config[project]["prix_seuil_euro_mwh"][0],
        puissance_chaudiere_elec_mw=config[project]["puissance_chaudiere_elec_mw"],
        capacite_min_gaz_kwhth=config[project]["capacite_min_gaz_kwhth"],
        # timestamp_col="measured_at_utc",  # optionnel si non détectable
        value_col="steam_production_kwhth",  # optionnel si non détectable
    )
    return paths