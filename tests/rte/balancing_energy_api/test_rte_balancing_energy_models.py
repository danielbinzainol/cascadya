from __future__ import annotations

from src.rte.balancing_energy_api.rte_balancing_energy_models import ImbalanceDataResponse


def _imbalance_payload() -> dict:
    return {
        "imbalance_data": [
            {
                "start_date": "2026-03-20T00:00:00+01:00",
                "end_date": "2026-03-21T00:00:00+01:00",
                "resolution": "PT15M",
                "values": [
                    {
                        "start_date": "2026-03-20T00:00:00+01:00",
                        "end_date": "2026-03-20T00:15:00+01:00",
                        "imbalance": 200,
                        "system_trend": "Hausse",
                        "positive_imbalance_settlement_price": 45.55,
                        "negative_imbalance_settlement_price": 42.27,
                        "missing_data_list": "none",
                        "updated_date": "2026-03-20T00:30:00+01:00",
                    }
                ],
            }
        ]
    }


def test_imbalance_data_response_parses_expected_fields() -> None:
    parsed = ImbalanceDataResponse.model_validate(_imbalance_payload())

    assert len(parsed.imbalance_data) == 1
    assert parsed.imbalance_data[0].resolution == "PT15M"
    assert parsed.imbalance_data[0].values[0].imbalance == 200
    assert parsed.imbalance_data[0].values[0].positive_imbalance_settlement_price == 45.55


def test_imbalance_data_response_accepts_extra_fields() -> None:
    payload = _imbalance_payload()
    payload["imbalance_data"][0]["unexpected_field"] = "kept"
    payload["imbalance_data"][0]["values"][0]["another_unknown_field"] = "kept-too"

    parsed = ImbalanceDataResponse.model_validate(payload)

    assert parsed.imbalance_data[0].values[0].imbalance == 200
