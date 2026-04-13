from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.forecast_backoffice as fb


def _build_test_client(
    tmp_path: Path, monkeypatch
) -> tuple[TestClient, fb.ForecastManager]:
    (tmp_path / "data" / "inariz" / "raw").mkdir(parents=True, exist_ok=True)
    manager = fb.ForecastManager(data_root=tmp_path)
    app = FastAPI()

    @app.on_event("startup")
    async def startup() -> None:
        await manager.start()

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await manager.stop()

    app.include_router(fb.build_forecast_router(manager))
    return TestClient(app), manager


def test_create_run_and_read_details(tmp_path, monkeypatch) -> None:
    fake_series = pd.DataFrame(
        {
            "measured_at_utc": pd.date_range(
                "2026-01-01", periods=400, freq="15min", tz="UTC"
            ),
            "target": [float(i % 25) for i in range(400)],
        }
    )

    monkeypatch.setattr(
        fb, "_load_site_timeseries_from_workflow", lambda *_args, **_kwargs: fake_series
    )
    monkeypatch.setattr(
        fb,
        "_compute_single_model",
        lambda *_args, **_kwargs: {
            "metrics": {
                "mae": 1.0,
                "rmse": 2.0,
                "mape": 0.1,
                "r2": 0.9,
                "train_time_seconds": 0.01,
            },
            "in_sample_chart": [
                {
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "actual": 1.0,
                    "predicted": 1.1,
                }
            ],
            "out_of_sample_chart": [
                {
                    "timestamp": "2026-01-01T01:00:00+00:00",
                    "actual": 2.0,
                    "predicted": 2.1,
                }
            ],
            "residual_chart": [
                {"timestamp": "2026-01-01T01:00:00+00:00", "residual": -0.1}
            ],
            "export_rows": [
                {
                    "timestamp": "2026-01-01T01:00:00+00:00",
                    "segment": "out_of_sample",
                    "actual": 2.0,
                    "predicted": 2.1,
                }
            ],
        },
    )

    client, _ = _build_test_client(tmp_path, monkeypatch)
    with client:
        created = client.post(
            "/forecasts/runs",
            json={
                "site": "inariz",
                "model": "linear_regression",
                "n_splits": 3,
                "gap": 0,
                "test_size": 96,
            },
        )
        assert created.status_code == 200
        run_id = created.json()["run_id"]
        for _ in range(30):
            detail = client.get(f"/forecasts/runs/{run_id}")
            assert detail.status_code == 200
            if detail.json()["status"] == "done":
                break
            time.sleep(0.05)
        payload = detail.json()
        assert payload["status"] == "done"
        assert payload["metrics"]["rmse"] == 2.0
        export_response = client.get(f"/forecasts/runs/{run_id}/export")
        assert export_response.status_code == 200
        assert "text/csv" in export_response.headers["content-type"]


def test_runs_for_same_site_are_queued(tmp_path, monkeypatch) -> None:
    fake_series = pd.DataFrame(
        {
            "measured_at_utc": pd.date_range(
                "2026-01-01", periods=400, freq="15min", tz="UTC"
            ),
            "target": [float(i) for i in range(400)],
        }
    )

    monkeypatch.setattr(
        fb, "_load_site_timeseries_from_workflow", lambda *_args, **_kwargs: fake_series
    )

    def slow_compute(*_args, **_kwargs):
        time.sleep(0.2)
        return {
            "metrics": {
                "mae": 1.0,
                "rmse": 3.0,
                "mape": 0.2,
                "r2": 0.8,
                "train_time_seconds": 0.2,
            },
            "in_sample_chart": [],
            "out_of_sample_chart": [],
            "residual_chart": [],
            "export_rows": [],
        }

    monkeypatch.setattr(fb, "_compute_single_model", slow_compute)
    client, _ = _build_test_client(tmp_path, monkeypatch)
    with client:
        first = client.post(
            "/forecasts/runs",
            json={
                "site": "inariz",
                "model": "simple_copy",
                "n_splits": 3,
                "gap": 0,
                "test_size": 96,
            },
        )
        second = client.post(
            "/forecasts/runs",
            json={
                "site": "inariz",
                "model": "median_copy",
                "n_splits": 3,
                "gap": 0,
                "test_size": 96,
            },
        )
        assert first.status_code == 200
        assert second.status_code == 200
        second_run_id = second.json()["run_id"]
        queued = client.get(f"/forecasts/runs/{second_run_id}")
        assert queued.status_code == 200
        assert queued.json()["queue_position"] >= 1


def test_all_models_ranking_is_persisted(tmp_path, monkeypatch) -> None:
    fake_series = pd.DataFrame(
        {
            "measured_at_utc": pd.date_range(
                "2026-01-01", periods=400, freq="15min", tz="UTC"
            ),
            "target": [float(i % 10) for i in range(400)],
        }
    )
    monkeypatch.setattr(
        fb, "_load_site_timeseries_from_workflow", lambda *_args, **_kwargs: fake_series
    )

    def fake_compute(model_name, *_args, **_kwargs):
        rmse = {"simple_copy": 4.0, "median_copy": 2.5, "linear_regression": 1.5}.get(
            model_name, 9.9
        )
        return {
            "metrics": {
                "mae": 1.0,
                "rmse": rmse,
                "mape": 0.1,
                "r2": 0.7,
                "train_time_seconds": 0.02,
            },
            "in_sample_chart": [],
            "out_of_sample_chart": [],
            "residual_chart": [],
            "export_rows": [],
        }

    monkeypatch.setattr(fb, "_compute_single_model", fake_compute)
    client, _ = _build_test_client(tmp_path, monkeypatch)
    with client:
        created = client.post(
            "/forecasts/runs",
            json={
                "site": "inariz",
                "model": "all_models",
                "n_splits": 3,
                "gap": 0,
                "test_size": 96,
            },
        )
        assert created.status_code == 200
        run_id = created.json()["run_id"]
        for _ in range(40):
            detail = client.get(f"/forecasts/runs/{run_id}")
            if detail.json()["status"] == "done":
                break
            time.sleep(0.05)
        ranking = detail.json()["ranking"]
        assert ranking[0]["model"] == "linear_regression"
        assert ranking[0]["rmse"] == 1.5


def test_update_schedule_edits_existing_instead_of_creating_duplicate(
    tmp_path, monkeypatch
) -> None:
    client, _ = _build_test_client(tmp_path, monkeypatch)
    with client:
        created = client.post(
            "/forecasts/schedules",
            json={
                "site": "inariz",
                "model": "simple_copy",
                "n_splits": 3,
                "gap": 0,
                "test_size": 96,
                "active": True,
            },
        )
        assert created.status_code == 200
        schedule_id = created.json()["schedule_id"]

        updated = client.patch(
            f"/forecasts/schedules/{schedule_id}",
            json={
                "site": "inariz",
                "model": "median_copy",
                "n_splits": 4,
                "gap": 2,
                "test_size": 48,
                "active": False,
            },
        )
        assert updated.status_code == 200
        payload = updated.json()
        assert payload["schedule_id"] == schedule_id
        assert payload["model"] == "median_copy"
        assert payload["n_splits"] == 4
        assert payload["gap"] == 2
        assert payload["test_size"] == 48
        assert payload["active"] is False

        schedules = client.get("/forecasts/schedules")
        assert schedules.status_code == 200
        all_schedules = schedules.json()
        assert len(all_schedules) == 1
        assert all_schedules[0]["schedule_id"] == schedule_id
