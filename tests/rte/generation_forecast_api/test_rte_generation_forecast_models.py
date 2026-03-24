from __future__ import annotations

from src.rte.generation_forecast_api.rte_generation_forecast_models import GenerationForecastResponse


def _forecast_payload() -> dict:
    return {
        "forecasts": [
            {
                "production_type": "WIND",
                "type": "D-1",
                "start_date": "2026-03-20T00:00:00+01:00",
                "end_date": "2026-03-21T00:00:00+01:00",
                "values": [
                    {
                        "start_date": "2026-03-20T00:00:00+01:00",
                        "end_date": "2026-03-20T00:15:00+01:00",
                        "updated_date": "2026-03-20T00:20:00+01:00",
                        "value": 2450,
                    }
                ],
            }
        ]
    }


def test_generation_forecast_response_parses_forecasts_root_key() -> None:
    parsed = GenerationForecastResponse.model_validate(_forecast_payload())

    assert len(parsed.forecasts) == 1
    assert parsed.forecasts[0].production_type == "WIND"
    assert parsed.forecasts[0].type == "D-1"
    assert parsed.forecasts[0].values[0].value == 2450


def test_generation_forecast_response_accepts_generation_forecasts_root_key() -> None:
    payload = _forecast_payload()
    payload["generation_forecasts"] = payload.pop("forecasts")

    parsed = GenerationForecastResponse.model_validate(payload)

    assert len(parsed.forecasts) == 1
    assert parsed.forecasts[0].production_type == "WIND"


def test_generation_forecast_response_keeps_optional_fields_flexible() -> None:
    payload = _forecast_payload()
    payload["forecasts"][0]["unexpected_field"] = "kept"
    payload["forecasts"][0]["values"][0]["unknown_value_field"] = "kept-too"

    parsed = GenerationForecastResponse.model_validate(payload)

    assert parsed.forecasts[0].values[0].value == 2450
