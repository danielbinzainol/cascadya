from __future__ import annotations

import pandas as pd
import pytest

from src.aeolus_market_bridge import (
    infer_product_time_step,
    market_orders_dataframe_to_transactions,
    market_orders_paths_to_payload,
)
from src.aeolus_models import ProductTimeStepApi


def _market_orders_frame(
    timestamps: list[str], powers_kw: list[float], prices_max: list[float]
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "asset_id": ["inariz"] * len(timestamps),
            "Delivery_datetime(UTC_start_of_period)": timestamps,
            "Price_min(E_MWh)": [-500.0] * len(timestamps),
            "Price_max(E_MWh)": prices_max,
            "Power_in_kW(Sell)": powers_kw,
        }
    )


def test_infer_product_time_step_detects_quarter_hour() -> None:
    timestamps = pd.Series(
        pd.to_datetime(
            [
                "2026-02-11T00:00:00Z",
                "2026-02-11T00:15:00Z",
                "2026-02-11T00:30:00Z",
            ],
            utc=True,
        )
    )

    product_time_step = infer_product_time_step(timestamps)

    assert product_time_step == ProductTimeStepApi.QUARTER_OF_AN_HOUR


def test_market_orders_dataframe_to_transactions_converts_to_positive_quantities() -> (
    None
):
    orders = _market_orders_frame(
        timestamps=["2026-02-11 00:00:00", "2026-02-11 00:15:00"],
        powers_kw=[-180.2, 0.0],
        prices_max=[61.2, 61.2],
    )

    transactions = market_orders_dataframe_to_transactions(
        orders,
        farm_id=123,
        drop_zero_quantities=True,
    )

    assert len(transactions) == 1
    assert transactions[0].farm_id == 123
    assert transactions[0].quantity_in_kw == 180
    assert (
        transactions[0].market_product_time_step
        == ProductTimeStepApi.QUARTER_OF_AN_HOUR
    )


def test_market_orders_dataframe_to_transactions_rejects_mixed_time_steps() -> None:
    orders = _market_orders_frame(
        timestamps=[
            "2026-02-11 00:00:00",
            "2026-02-11 00:15:00",
            "2026-02-11 00:45:00",
        ],
        powers_kw=[-100.0, -100.0, -100.0],
        prices_max=[60.0, 60.0, 60.0],
    )

    with pytest.raises(ValueError, match="mixed time steps"):
        market_orders_dataframe_to_transactions(orders, farm_id=77)


def test_market_orders_paths_to_payload_aggregates_files(tmp_path) -> None:
    day_1 = _market_orders_frame(
        timestamps=["2026-02-11 00:00:00"],
        powers_kw=[-100.0],
        prices_max=[55.0],
    )
    day_2 = _market_orders_frame(
        timestamps=["2026-02-12 00:00:00"],
        powers_kw=[-200.0],
        prices_max=[56.0],
    )
    path_1 = tmp_path / "inariz_20260211_20260223_1735.csv"
    path_2 = tmp_path / "inariz_20260212_20260223_1735.csv"
    day_1.to_csv(path_1, sep=";", index=False)
    day_2.to_csv(path_2, sep=";", index=False)

    payload = market_orders_paths_to_payload([path_1, path_2], farm_id=42)

    assert len(payload.transactions) == 2
    assert [transaction.quantity_in_kw for transaction in payload.transactions] == [
        100,
        200,
    ]
