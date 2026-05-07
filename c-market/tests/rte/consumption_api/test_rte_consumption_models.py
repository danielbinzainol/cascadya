from __future__ import annotations

from pydantic import ValidationError
import pytest

from src.rte.consumption_api.rte_consumption_models import (
    ShortTermResponse,
    ShortTermResponseType,
)


def _short_term_payload(*, forecast_type: str = "REALISED") -> dict:
    return {
        "short_term": [
            {
                "type": forecast_type,
                "start_date": "2026-03-20T00:00:00+01:00",
                "end_date": "2026-03-21T00:00:00+01:00",
                "values": [
                    {
                        "start_date": "2026-03-20T00:00:00+01:00",
                        "end_date": "2026-03-20T00:15:00+01:00",
                        "updated_date": "2026-03-20T00:20:00+01:00",
                        "value": 52345,
                    }
                ],
            }
        ]
    }


def test_short_term_response_parses_with_realised_type() -> None:
    parsed = ShortTermResponse.model_validate(
        _short_term_payload(forecast_type="REALISED")
    )

    assert len(parsed.short_term) == 1
    assert parsed.short_term[0].type == ShortTermResponseType.REALISED
    assert parsed.short_term[0].values[0].value == 52345


def test_short_term_response_parses_with_actual_type() -> None:
    parsed = ShortTermResponse.model_validate(
        _short_term_payload(forecast_type="ACTUAL")
    )

    assert parsed.short_term[0].type == ShortTermResponseType.ACTUAL


def test_short_term_response_accepts_empty_values_list() -> None:
    payload = _short_term_payload()
    payload["short_term"][0]["values"] = []

    parsed = ShortTermResponse.model_validate(payload)

    assert parsed.short_term[0].values == []


def test_short_term_response_rejects_unknown_forecast_type() -> None:
    with pytest.raises(ValidationError):
        ShortTermResponse.model_validate(_short_term_payload(forecast_type="D-5"))
