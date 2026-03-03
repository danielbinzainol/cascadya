from __future__ import annotations

import datetime

import pytest
from pydantic import ValidationError

from src.aeolus_models import AssetTimeSeriesPoint, MaintenancePayload


def test_maintenance_payload_accepts_utc_datetimes() -> None:
    payload = MaintenancePayload(
        startDate=datetime.datetime(2026, 2, 1, 10, 0, tzinfo=datetime.UTC),
        endDate=datetime.datetime(2026, 2, 1, 11, 0, tzinfo=datetime.UTC),
        maintenanceNatureId=5,
        producingUnitIds=[123],
    )

    assert payload.start_date.utcoffset() == datetime.timedelta(0)
    assert payload.end_date.utcoffset() == datetime.timedelta(0)


def test_maintenance_payload_rejects_non_utc_datetimes() -> None:
    paris_offset = datetime.timezone(datetime.timedelta(hours=1))
    with pytest.raises(ValidationError, match="must be UTC"):
        MaintenancePayload(
            startDate=datetime.datetime(2026, 2, 1, 10, 0, tzinfo=paris_offset),
            endDate=datetime.datetime(2026, 2, 1, 11, 0, tzinfo=paris_offset),
            maintenanceNatureId=5,
            producingUnitIds=[123],
        )


def test_asset_time_series_point_rejects_non_utc_datetime() -> None:
    paris_offset = datetime.timezone(datetime.timedelta(hours=1))
    with pytest.raises(ValidationError, match="must be UTC"):
        AssetTimeSeriesPoint(
            datetime=datetime.datetime(2026, 2, 1, 10, 0, tzinfo=paris_offset),
            powerkW=100,
            timeStepMinutes=15,
        )
