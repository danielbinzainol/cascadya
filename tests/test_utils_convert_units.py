import pandas as pd
import pytest

from src.utils import (
    COEFF_KG_TO_KJ,
    COEFF_KJ_TO_KWH,
    COEFF_KWH_PCS_TO_KWH_PCI,
    COEFF_M3_TO_KG,
    COEFF_M3_TO_NM3,
    COEFF_NM3_TO_KWH_PCS,
    convert_gas_units,
    convert_saturated_steam_units,
)

def test_convert_saturated_steam_units_from_m3_to_kwh_th() -> None:
    df = pd.DataFrame({"steam_m3": [1.0, 2.0]})

    result = convert_saturated_steam_units(
        df=df,
        value_col="steam_m3",
        converted_value_col="steam_kwh_th",
        initial_unit="m3",
        target_unit="kWh th",
    )

    factor = COEFF_M3_TO_KG * COEFF_KG_TO_KJ * COEFF_KJ_TO_KWH
    expected = [1.0 * factor, 2.0 * factor]
    assert result["steam_kwh_th"].tolist() == pytest.approx(expected)


def test_convert_saturated_steam_units_rejects_invalid_initial_unit() -> None:
    df = pd.DataFrame({"value": [1.0]})

    with pytest.raises(ValueError, match="initial_unit"):
        convert_saturated_steam_units(
            df=df,
            value_col="value",
            converted_value_col="converted",
            initial_unit="bar",
            target_unit="kWh th",
        )


def test_convert_saturated_steam_units_rejects_identical_units() -> None:
    df = pd.DataFrame({"value": [1.0]})

    with pytest.raises(ValueError, match="identical"):
        convert_saturated_steam_units(
            df=df,
            value_col="value",
            converted_value_col="converted",
            initial_unit="m3",
            target_unit="m3",
        )


def test_convert_gas_units_from_m3_to_kwh_pci() -> None:
    df = pd.DataFrame({"gas_m3": [1.0, 2.0]})

    result = convert_gas_units(
        df=df,
        value_col="gas_m3",
        converted_value_col="gas_kwh_pci",
        initial_unit="m3",
        target_unit="kWh PCI",
    )

    factor = COEFF_M3_TO_NM3 * COEFF_NM3_TO_KWH_PCS * COEFF_KWH_PCS_TO_KWH_PCI
    expected = [1.0 * factor, 2.0 * factor]
    assert result["gas_kwh_pci"].tolist() == pytest.approx(expected)


def test_convert_gas_units_rejects_identical_units() -> None:
    df = pd.DataFrame({"value": [1.0]})

    with pytest.raises(ValueError, match="identical"):
        convert_gas_units(
            df=df,
            value_col="value",
            converted_value_col="converted",
            initial_unit="m3",
            target_unit="m3",
        )


def test_convert_gas_units_rejects_invalid_target_unit() -> None:
    df = pd.DataFrame({"value": [1.0]})

    with pytest.raises(ValueError, match="target_unit"):
        convert_gas_units(
            df=df,
            value_col="value",
            converted_value_col="converted",
            initial_unit="m3",
            target_unit="MWh",
        )
