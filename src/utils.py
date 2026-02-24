import yaml
from pathlib import Path
import pandas as pd

# coefficients de conversion venant de Tarkett, todo rendre modulables
# todo je crois qu'ils sont mal nommés, pas dans le bon ordre, vu que les 2 aboutissent à NM3.
COEFF_M3_NM3 = 1.2
COEFF_PCS_KWH_NM3 = 11.35

def load_config():
    config_path = Path(__file__).resolve().parent.parent / "config.yml"  # uses src/config.yml
    with config_path.open("r", encoding='utf-8') as file:
        config = yaml.safe_load(file)
        return config
    
def convert_m3_to_mwhth(
    df: pd.DataFrame,
    value_col: str,
    converted_value_col:str, #must include the unit in the name
    coeff_m3_nm3: float = COEFF_M3_NM3,
    coeff_pcs_kwh_nm3: float = COEFF_PCS_KWH_NM3,
    ) -> pd.DataFrame:
    df = df.copy()
    # df[converted_value_col] = df[value_col] * coeff_m3_nm3 * coeff_pcs_kwh_nm3 / 1000
    # Temp et faux, le temps de tester la creation des market orders, car je ne sais pas comment convertir la vapeur. Todo corriger
    df[converted_value_col] = df[value_col] * coeff_m3_nm3 / 1000
    return df    