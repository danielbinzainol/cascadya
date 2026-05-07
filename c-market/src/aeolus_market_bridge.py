from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.aeolus_models import (
    AllowedMarket,
    AllowedTransactionType,
    MarketFarmTransactionsCreate,
    PositionType,
    ProductTimeStepApi,
    TransactionCreate,
)
from src.market_orders import ORDER_HEADER

DELIVERY_DATETIME_COL = "Delivery_datetime(UTC_start_of_period)"
PRICE_MIN_COL = "Price_min(E_MWh)"
PRICE_MAX_COL = "Price_max(E_MWh)"
POWER_SELL_COL = "Power_in_kW(Sell)"
SUPPORTED_PRODUCT_TIME_STEP_MINUTES = {
    15: ProductTimeStepApi.QUARTER_OF_AN_HOUR,
    60: ProductTimeStepApi.HOUR,
}


def infer_product_time_step(
    datetimes: pd.Series,
    *,
    default_product_time_step: ProductTimeStepApi = ProductTimeStepApi.QUARTER_OF_AN_HOUR,
) -> ProductTimeStepApi:
    timestamps = (
        pd.to_datetime(datetimes, utc=True, errors="raise")
        .sort_values()
        .drop_duplicates()
    )
    if timestamps.size <= 1:
        return default_product_time_step
    deltas_minutes = (
        timestamps.diff()
        .dropna()
        .dt.total_seconds()
        .div(60)
        .round()
        .astype(int)
        .unique()
        .tolist()
    )
    if len(deltas_minutes) != 1:
        raise ValueError(f"Market orders contain mixed time steps: {deltas_minutes}")
    time_step_minutes = deltas_minutes[0]
    if time_step_minutes not in SUPPORTED_PRODUCT_TIME_STEP_MINUTES:
        raise ValueError(
            f"Unsupported time step {time_step_minutes} minutes. "
            "Aeolus transactions support 15 and 60 minutes product time steps."
        )
    return SUPPORTED_PRODUCT_TIME_STEP_MINUTES[time_step_minutes]


def market_orders_dataframe_to_transactions(
    market_orders: pd.DataFrame,
    *,
    farm_id: int,
    market: AllowedMarket = AllowedMarket.DAY_AHEAD,
    transaction_type: AllowedTransactionType = AllowedTransactionType.MARKET,
    position_type: PositionType = PositionType.PURCHASE,
    default_product_time_step: ProductTimeStepApi = ProductTimeStepApi.QUARTER_OF_AN_HOUR,
    drop_zero_quantities: bool = True,
) -> list[TransactionCreate]:
    if farm_id <= 0:
        raise ValueError("farm_id must be a positive integer.")

    missing_columns = [
        column_name
        for column_name in ORDER_HEADER
        if column_name not in market_orders.columns
    ]
    if missing_columns:
        raise ValueError(f"Missing market order columns: {missing_columns}")

    working = market_orders[ORDER_HEADER].copy()
    working[DELIVERY_DATETIME_COL] = pd.to_datetime(
        working[DELIVERY_DATETIME_COL], utc=True, errors="raise"
    )
    product_time_step = infer_product_time_step(
        working[DELIVERY_DATETIME_COL],
        default_product_time_step=default_product_time_step,
    )

    transactions: list[TransactionCreate] = []
    for row in working.to_dict(orient="records"):
        power_sell_kw = float(row[POWER_SELL_COL])
        quantity_kw = int(round(abs(power_sell_kw)))
        if quantity_kw < 0:
            raise ValueError("Computed transaction quantity cannot be negative.")
        if quantity_kw == 0 and drop_zero_quantities:
            continue
        if quantity_kw == 0:
            raise ValueError("Aeolus transactions require quantityInkW > 0.")

        delivery_datetime = row[DELIVERY_DATETIME_COL]
        if delivery_datetime.tzinfo is None:
            raise ValueError(
                "Delivery_datetime(UTC_start_of_period) must include timezone information."
            )

        transaction = TransactionCreate(
            farmId=farm_id,
            dateApplicationStart=delivery_datetime.to_pydatetime(),
            marketProductTimeStep=product_time_step,
            quantityInkW=quantity_kw,
            priceInEuroByMwh=float(row[PRICE_MAX_COL]),
            positionType=position_type,
            market=market,
            transactionType=transaction_type,
        )
        transactions.append(transaction)
    return transactions


def market_orders_csv_to_transactions(
    csv_path: str | Path,
    *,
    farm_id: int,
    market: AllowedMarket = AllowedMarket.DAY_AHEAD,
    transaction_type: AllowedTransactionType = AllowedTransactionType.MARKET,
    position_type: PositionType = PositionType.PURCHASE,
    default_product_time_step: ProductTimeStepApi = ProductTimeStepApi.QUARTER_OF_AN_HOUR,
    drop_zero_quantities: bool = True,
    sep: str = ";",
) -> list[TransactionCreate]:
    orders = pd.read_csv(csv_path, sep=sep)
    return market_orders_dataframe_to_transactions(
        orders,
        farm_id=farm_id,
        market=market,
        transaction_type=transaction_type,
        position_type=position_type,
        default_product_time_step=default_product_time_step,
        drop_zero_quantities=drop_zero_quantities,
    )


def market_orders_paths_to_payload(
    csv_paths: list[Path],
    *,
    farm_id: int,
    market: AllowedMarket = AllowedMarket.DAY_AHEAD,
    transaction_type: AllowedTransactionType = AllowedTransactionType.MARKET,
    position_type: PositionType = PositionType.PURCHASE,
    default_product_time_step: ProductTimeStepApi = ProductTimeStepApi.QUARTER_OF_AN_HOUR,
    drop_zero_quantities: bool = True,
    sep: str = ";",
) -> MarketFarmTransactionsCreate:
    transactions: list[TransactionCreate] = []
    for csv_path in csv_paths:
        transactions.extend(
            market_orders_csv_to_transactions(
                csv_path,
                farm_id=farm_id,
                market=market,
                transaction_type=transaction_type,
                position_type=position_type,
                default_product_time_step=default_product_time_step,
                drop_zero_quantities=drop_zero_quantities,
                sep=sep,
            )
        )
    return MarketFarmTransactionsCreate(transactions=transactions)
