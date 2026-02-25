import pandas as pd
import pytest

from ..market_orders import ORDER_HEADER, build_market_orders


def _forecast(
    timestamps: pd.DatetimeIndex | pd.Series,
    values: list[float],
    value_col: str = "steam_production_kwhth",
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "measured_at_utc": timestamps,
            value_col: values,
        }
    )


def test_build_market_orders_rejects_non_utc_timezone(tmp_path):
    forecast = _forecast(
        pd.date_range("2026-02-11 00:00:00", periods=2, freq="15min", tz="Europe/Paris"),
        [100.0, 120.0],
    )

    with pytest.raises(ValueError, match="Missing or wrong tzinfo"):
        build_market_orders(
            project_name="inariz",
            forecast=forecast,
            prix_seuil_euro_mwh=58.0,
            puissance_chaudiere_elec_mw=2.0,
            capacite_min_gaz_kwhth=50.0,
            value_col="steam_production_kwhth",
            output_dir=tmp_path,
        )


def test_build_market_orders_rejects_nan_timestamp(tmp_path):
    timestamps = pd.to_datetime(
        ["2026-02-11 00:00:00", None],
        utc=True,
    )
    forecast = _forecast(timestamps, [100.0, 120.0])

    with pytest.raises(ValueError, match="NaN values in timestamp or value columns"):
        build_market_orders(
            project_name="inariz",
            forecast=forecast,
            prix_seuil_euro_mwh=58.0,
            puissance_chaudiere_elec_mw=2.0,
            capacite_min_gaz_kwhth=50.0,
            value_col="steam_production_kwhth",
            output_dir=tmp_path,
        )


def test_build_market_orders_rejects_nan_value(tmp_path):
    forecast = _forecast(
        pd.date_range("2026-02-11 00:00:00", periods=2, freq="15min", tz="UTC"),
        [100.0, float("nan")],
    )

    with pytest.raises(ValueError, match="NaN values in timestamp or value columns"):
        build_market_orders(
            project_name="inariz",
            forecast=forecast,
            prix_seuil_euro_mwh=58.0,
            puissance_chaudiere_elec_mw=2.0,
            capacite_min_gaz_kwhth=50.0,
            value_col="steam_production_kwhth",
            output_dir=tmp_path,
        )


def test_build_market_orders_computes_clipping_and_negative_sign(tmp_path):
    # available_kwhth = (value - 100).clip(lower=0)
    # power_kw = available_kwhth * 4, clipped to 2000 (2 MW)
    # sell = -power_kw
    forecast = _forecast(
        pd.date_range("2026-02-11 00:00:00", periods=3, freq="15min", tz="UTC"),
        [50.0, 150.0, 1000.0],
    )

    paths = build_market_orders(
        project_name="inariz",
        forecast=forecast,
        prix_seuil_euro_mwh=58.0,
        puissance_chaudiere_elec_mw=2.0,
        capacite_min_gaz_kwhth=100.0,
        value_col="steam_production_kwhth",
        output_dir=tmp_path,
        run_at=pd.Timestamp("2026-02-23 17:35:00", tz="UTC"),
    )

    assert len(paths) == 1
    out = pd.read_csv(paths[0], sep=";")
    assert out["Power_in_kW(Sell)"].tolist() == pytest.approx([0.0, -200.0, -2000.0])
    assert (out["Power_in_kW(Sell)"] <= 0).all()


def test_build_market_orders_splits_files_by_day_and_uses_expected_names(tmp_path):
    forecast = _forecast(
        pd.to_datetime(
            [
                "2026-02-11 23:45:00",
                "2026-02-12 00:00:00",
                "2026-02-12 00:15:00",
            ],
            utc=True,
        ),
        [500.0, 500.0, 500.0],
    )

    paths = build_market_orders(
        project_name="inariz",
        forecast=forecast,
        prix_seuil_euro_mwh=58.0,
        puissance_chaudiere_elec_mw=2.0,
        capacite_min_gaz_kwhth=100.0,
        value_col="steam_production_kwhth",
        output_dir=tmp_path,
        run_at=pd.Timestamp("2026-02-23 17:35:00", tz="UTC"),
    )

    names = sorted(path.name for path in paths)
    assert names == [
        "inariz_20260211_20260223_1735.csv",
        "inariz_20260212_20260223_1735.csv",
    ]


def test_build_market_orders_writes_exact_order_header(tmp_path):
    forecast = _forecast(
        pd.date_range("2026-02-11 00:00:00", periods=2, freq="15min", tz="UTC"),
        [300.0, 400.0],
    )

    paths = build_market_orders(
        project_name="inariz",
        forecast=forecast,
        prix_seuil_euro_mwh=58.0,
        puissance_chaudiere_elec_mw=2.0,
        capacite_min_gaz_kwhth=100.0,
        value_col="steam_production_kwhth",
        output_dir=tmp_path,
        run_at=pd.Timestamp("2026-02-23 17:35:00", tz="UTC"),
    )

    out = pd.read_csv(paths[0], sep=";")
    assert list(out.columns) == ORDER_HEADER
