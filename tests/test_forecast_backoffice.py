from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.backoffice.forecasts.manager as forecast_manager
from src.backoffice.forecasts.router import build_forecast_router


def _build_test_client(
    tmp_path: Path, monkeypatch
) -> tuple[TestClient, forecast_manager.ForecastManager]:
    (tmp_path / "data" / "inariz" / "raw").mkdir(parents=True, exist_ok=True)
    manager = forecast_manager.ForecastManager(data_root=tmp_path)
    app = FastAPI()

    @app.on_event("startup")
    async def startup() -> None:
        await manager.start()

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await manager.stop()

    app.include_router(build_forecast_router(manager))
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
        forecast_manager,
        "_load_site_timeseries_from_workflow",
        lambda *_args, **_kwargs: fake_series,
    )
    monkeypatch.setattr(
        forecast_manager,
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
        forecast_manager,
        "_load_site_timeseries_from_workflow",
        lambda *_args, **_kwargs: fake_series,
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

    monkeypatch.setattr(forecast_manager, "_compute_single_model", slow_compute)
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
        forecast_manager,
        "_load_site_timeseries_from_workflow",
        lambda *_args, **_kwargs: fake_series,
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

    monkeypatch.setattr(forecast_manager, "_compute_single_model", fake_compute)
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


def test_schedule_activate_deactivate_and_delete(tmp_path, monkeypatch) -> None:
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

        deactivated = client.patch(
            f"/forecasts/schedules/{schedule_id}/active",
            json={"active": False},
        )
        assert deactivated.status_code == 200
        assert deactivated.json()["active"] is False

        activated = client.patch(
            f"/forecasts/schedules/{schedule_id}/active",
            json={"active": True},
        )
        assert activated.status_code == 200
        assert activated.json()["active"] is True

        deleted = client.delete(f"/forecasts/schedules/{schedule_id}")
        assert deleted.status_code == 200
        assert deleted.json()["status"] == "deleted"

        missing_delete = client.delete(f"/forecasts/schedules/{schedule_id}")
        assert missing_delete.status_code == 404
        assert "Unknown schedule" in missing_delete.json()["detail"]


def test_run_details_include_scoring_details_and_export_filename(
    tmp_path, monkeypatch
) -> None:
    fake_series = pd.DataFrame(
        {
            "measured_at_utc": pd.date_range(
                "2026-01-01", periods=300, freq="15min", tz="UTC"
            ),
            "target": [float(i % 17) for i in range(300)],
        }
    )
    monkeypatch.setattr(
        forecast_manager,
        "_load_site_timeseries_from_workflow",
        lambda *_args, **_kwargs: fake_series,
    )

    def fake_compute(model_name, *_args, **_kwargs):
        base_rmse = {
            "simple_copy": 2.0,
            "median_copy": 1.8,
            "linear_regression": 1.2,
        }.get(model_name, 9.9)
        return {
            "metrics": {
                "mae": 1.0,
                "rmse": base_rmse,
                "mape": 0.2,
                "r2": 0.5,
                "train_time_seconds": 0.03,
            },
            "fold_details": [
                {
                    "fold": 1,
                    "train_start": "2026-01-01 00:00:00+00:00",
                    "train_end": "2026-01-02 00:00:00+00:00",
                    "test_start": "2026-01-02 00:15:00+00:00",
                    "test_end": "2026-01-03 00:00:00+00:00",
                    "test_std": 3.2,
                    "model_rmse": {model_name: base_rmse},
                },
                {
                    "fold": 2,
                    "train_start": "2026-01-01 00:00:00+00:00",
                    "train_end": "2026-01-03 00:00:00+00:00",
                    "test_start": "2026-01-03 00:15:00+00:00",
                    "test_end": "2026-01-04 00:00:00+00:00",
                    "test_std": 2.7,
                    "model_rmse": {model_name: base_rmse + 0.5},
                },
            ],
            "in_sample_chart": [
                {
                    "timestamp": "2026-01-03T00:00:00+00:00",
                    "actual": 10.0,
                    "predicted": 9.8,
                }
            ],
            "out_of_sample_chart": [
                {
                    "timestamp": "2026-01-04T00:15:00+00:00",
                    "actual": None,
                    "predicted": 11.1,
                }
            ],
            "residual_chart": [
                {"timestamp": "2026-01-03T00:00:00+00:00", "residual": 0.2}
            ],
            "export_rows": [
                {
                    "timestamp": "2026-01-04T00:15:00+00:00",
                    "segment": "out_of_sample",
                    "actual": None,
                    "predicted": 11.1,
                }
            ],
        }

    monkeypatch.setattr(forecast_manager, "_compute_single_model", fake_compute)

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

        detail_payload = None
        for _ in range(50):
            detail = client.get(f"/forecasts/runs/{run_id}")
            assert detail.status_code == 200
            detail_payload = detail.json()
            if detail_payload["status"] == "done":
                break
            time.sleep(0.05)
        assert detail_payload is not None
        assert detail_payload["status"] == "done"
        assert len(detail_payload["scoring_details"]) == 2
        assert set(detail_payload["scoring_details"][0]["model_rmse"].keys()) >= {
            "simple_copy",
            "median_copy",
            "linear_regression",
        }

        export_resp = client.get(f"/forecasts/runs/{run_id}/export")
        assert export_resp.status_code == 200
        content_disposition = export_resp.headers.get("content-disposition", "")
        assert "forecast_inariz_" in content_disposition
        assert "_all_models_ns3_g0_ts96.csv" in content_disposition


def test_run_detail_handles_nan_payload_without_500(tmp_path, monkeypatch) -> None:
    fake_series = pd.DataFrame(
        {
            "measured_at_utc": pd.date_range(
                "2026-01-01", periods=220, freq="15min", tz="UTC"
            ),
            "target": [float(i % 11) for i in range(220)],
        }
    )
    monkeypatch.setattr(
        forecast_manager,
        "_load_site_timeseries_from_workflow",
        lambda *_args, **_kwargs: fake_series,
    )

    monkeypatch.setattr(
        forecast_manager,
        "_compute_single_model",
        lambda *_args, **_kwargs: {
            "metrics": {
                "mae": 1.0,
                "rmse": 1.23,
                "mape": 0.1,
                "r2": float("nan"),
                "train_time_seconds": 0.01,
            },
            "fold_details": [],
            "in_sample_chart": [
                {
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "actual": 1.0,
                    "predicted": float("nan"),
                }
            ],
            "out_of_sample_chart": [
                {
                    "timestamp": "2026-01-01T00:15:00+00:00",
                    "actual": None,
                    "predicted": float("nan"),
                }
            ],
            "residual_chart": [
                {"timestamp": "2026-01-01T00:00:00+00:00", "residual": float("nan")}
            ],
            "export_rows": [
                {
                    "timestamp": "2026-01-01T00:15:00+00:00",
                    "segment": "out_of_sample",
                    "actual": None,
                    "predicted": 0.0,
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
                "model": "simple_copy",
                "n_splits": 3,
                "gap": 0,
                "test_size": 96,
            },
        )
        assert created.status_code == 200
        run_id = created.json()["run_id"]

        payload = None
        for _ in range(50):
            detail = client.get(f"/forecasts/runs/{run_id}")
            assert detail.status_code == 200
            payload = detail.json()
            if payload["status"] == "done":
                break
            time.sleep(0.05)
        assert payload is not None
        assert payload["status"] == "done"
        assert payload["metrics"]["rmse"] == 1.23
        assert payload["metrics"]["r2"] is None
