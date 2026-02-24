import yaml
from pathlib import Path
import pandas as pd

# coefficients de conversion venant de Tarkett, todo rendre modulables
# todo je crois qu'ils sont mal nommés, pas dans le bon ordre, vu que les 2 aboutissent à NM3.
COEFF_M3_TO_NM3 = 1.2 # dépendent de pression et température du gaz, ceux-là sont pour Tarkett.
COEFF_NM3_TO_KWH_PCS = 11.35
COEFF_KWH_PCS_TO_KWH_PCI = 0.89 #sauf si c'est une chaudière à condensation
COEFF_BOILER_EFFICIENCY = 0.95

ACCEPTED_GAS_UNITS = ["m3", "Nm3", "kWh PCS", "kWh PCI" "kWh PCI after boiler efficiency"]

# coefficients venant de Inariz
# en estimant que leur pression moyenne est de 5.5 bar relatifs, ce qui est faux
# PRESSION_CHAUDIERE_BAR_RELATIF = 5.5
# MASSE_VOLUMIQUE_VAPEUR_SATUREE_KG_PAR_M3 = 3.419 # A 6.5 BAR ABSOLU
COEFF_M3_TO_KG = 3.419
# CHALEUR_LATENTE_DE_VAPORISATION_KJ_PAR_KG = 2074,73 # A 6.5 BAR ABSOLU
COEFF_KG_TO_KJ = 2074.73
COEFF_KJ_TO_KWH = 1/3600

ACCEPTED_SATURATED_STEAM_UNITS = ["m3", "kg", "kJ", "kWh th"]

def load_config():
    config_path = Path(__file__).resolve().parent.parent / "config.yml"  # uses src/config.yml
    with config_path.open("r", encoding='utf-8') as file:
        config = yaml.safe_load(file)
        return config
    
def convert_gas_units(
    df: pd.DataFrame,
    value_col: str,
    converted_value_col:str, #must include the unit in the name
    initial_unit: str,
    target_unit: str,
    coeff_m3_to_nm3: float = COEFF_M3_TO_NM3,
    coeff_nm3_to_kwh_pcs: float = COEFF_NM3_TO_KWH_PCS,
    coeff_kwh_pcs_to_kwh_pci: float = COEFF_KWH_PCS_TO_KWH_PCI,
    coeff_boiler_efficiency: float = COEFF_BOILER_EFFICIENCY,
    ) -> pd.DataFrame:

    if initial_unit not in ACCEPTED_GAS_UNITS:
        raise ValueError(f"initial_unit {initial_unit} not in {ACCEPTED_GAS_UNITS}")
    if target_unit not in ACCEPTED_GAS_UNITS:
        raise ValueError(f"target_unit {target_unit} not in {ACCEPTED_GAS_UNITS}")
    if initial_unit == target_unit:
        raise ValueError(f"initial_unit and target_unit are identical")
    
    conversion_scales = {
        "m3": 1, 
        "Nm3": coeff_m3_to_nm3, 
        "kWh PCS": coeff_m3_to_nm3*coeff_nm3_to_kwh_pcs, 
        "kWh PCI": coeff_m3_to_nm3*coeff_nm3_to_kwh_pcs*coeff_kwh_pcs_to_kwh_pci, 
        "kWh PCI after boiler efficiency": coeff_m3_to_nm3*coeff_nm3_to_kwh_pcs*coeff_kwh_pcs_to_kwh_pci*coeff_boiler_efficiency
        }
        
    df = df.copy()
    df[converted_value_col] = df[value_col] * conversion_scales[target_unit] / conversion_scales[initial_unit]

    return df    


def convert_saturated_steam_units(
    df: pd.DataFrame,
    value_col: str,
    converted_value_col:str, #must include the unit in the name
    initial_unit: str,
    target_unit: str,
    coeff_m3_to_kg: float = COEFF_M3_TO_KG,
    coeff_kg_to_kj: float = COEFF_KG_TO_KJ,
    coeff_kj_to_kwh: float = COEFF_KJ_TO_KWH,
) -> pd.DataFrame:
    
    if initial_unit not in ACCEPTED_SATURATED_STEAM_UNITS:
        raise ValueError(f"initial_unit {initial_unit} not in {ACCEPTED_SATURATED_STEAM_UNITS}")
    if target_unit not in ACCEPTED_SATURATED_STEAM_UNITS:
        raise ValueError(f"target_unit {target_unit} not in {ACCEPTED_SATURATED_STEAM_UNITS}")
    if initial_unit == target_unit:
        raise ValueError(f"initial_unit and target_unit are identical")

    conversion_scales = {
        "m3": 1, 
        "kg": coeff_m3_to_kg, 
        "kJ": coeff_m3_to_kg*coeff_kg_to_kj , 
        "kWh th": coeff_m3_to_kg*coeff_kg_to_kj*coeff_kj_to_kwh, 
        }
        
    df = df.copy()
    df[converted_value_col] = df[value_col] * conversion_scales[target_unit] / conversion_scales[initial_unit]

    return df
