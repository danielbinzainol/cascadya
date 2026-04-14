from __future__ import annotations

import io

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from src.ml_models.forecasts.manager import ForecastManager
from src.ml_models.forecasts.models import FORECAST_TAB_HTML, PARIS_TZ, ForecastRun
from src.ml_models.forecasts.schemas import (
    RUN_STATUSES,
    RunCreateRequest,
    RunDetailResponse,
    RunSummaryResponse,
    ScheduleActiveUpdateRequest,
    ScheduleCreateRequest,
    ScheduleResponse,
    ScheduleUpdateRequest,
)


def _to_summary(run: ForecastRun) -> RunSummaryResponse:
    return RunSummaryResponse(
        run_id=run.run_id,
        site=run.site,
        model=run.model,
        trigger_source=run.trigger_source,
        status=run.status,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        queue_position=run.queue_position,
    )


def _to_detail(run: ForecastRun) -> RunDetailResponse:
    base = _to_summary(run)
    return RunDetailResponse(
        **base.model_dump(),
        n_splits=run.n_splits,
        gap=run.gap,
        test_size=run.test_size,
        ranking=run.ranking,
        metrics=run.metrics,
        scoring_details=run.scoring_details,
        in_sample_chart=run.in_sample_chart,
        out_of_sample_chart=run.out_of_sample_chart,
        residual_chart=run.residual_chart,
        logs=run.logs,
        error=run.error,
    )


def build_forecast_router(manager: ForecastManager) -> APIRouter:
    router = APIRouter(prefix="/forecasts", tags=["forecasts"])

    @router.get("/tab")
    async def forecasts_tab() -> FileResponse:
        if not FORECAST_TAB_HTML.exists():
            raise HTTPException(
                status_code=500, detail="Forecast UI assets are missing."
            )
        return FileResponse(FORECAST_TAB_HTML)

    @router.get("/sites")
    async def list_sites() -> dict[str, list[str]]:
        return {"sites": manager.available_sites()}

    @router.post("/runs", response_model=RunSummaryResponse)
    async def create_run(payload: RunCreateRequest) -> RunSummaryResponse:
        run = await manager.create_run(payload, trigger_source="manual")
        return _to_summary(run)

    @router.get("/runs", response_model=list[RunSummaryResponse])
    async def list_runs(
        site: str | None = None, status: RUN_STATUSES | None = None
    ) -> list[RunSummaryResponse]:
        runs = await manager.list_runs(site=site, status=status)
        return [_to_summary(r) for r in runs]

    @router.get("/runs/{run_id}", response_model=RunDetailResponse)
    async def get_run(run_id: str) -> RunDetailResponse:
        run = await manager.get_run(run_id)
        return _to_detail(run)

    @router.get("/runs/{run_id}/export")
    async def export_run(run_id: str) -> StreamingResponse:
        run = await manager.get_run(run_id)
        if run.status != "done" or not run.csv_buffer:
            raise HTTPException(
                status_code=409, detail="Run result not available for export."
            )
        buf = io.BytesIO(run.csv_buffer.encode("utf-8"))
        created = run.created_at.astimezone(PARIS_TZ).strftime("%Y%m%d_%H%M%S")
        filename = (
            f"forecast_{run.site}_{created}_{run.model}"
            f"_ns{run.n_splits}_g{run.gap}_ts{run.test_size}.csv"
        )
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return StreamingResponse(buf, media_type="text/csv", headers=headers)

    @router.post("/schedules", response_model=ScheduleResponse)
    async def create_schedule(payload: ScheduleCreateRequest) -> ScheduleResponse:
        schedule = await manager.create_schedule(payload)
        return ScheduleResponse(
            schedule_id=schedule.schedule_id,
            site=schedule.site,
            model=schedule.model,
            n_splits=schedule.n_splits,
            gap=schedule.gap,
            test_size=schedule.test_size,
            active=schedule.active,
            trigger_time=schedule.trigger_time.isoformat(timespec="minutes"),
            timezone=schedule.timezone,
            last_triggered_at=schedule.last_triggered_at,
        )

    @router.patch("/schedules/{schedule_id}", response_model=ScheduleResponse)
    async def update_schedule(
        schedule_id: str, payload: ScheduleUpdateRequest
    ) -> ScheduleResponse:
        schedule = await manager.update_schedule(schedule_id, payload)
        return ScheduleResponse(
            schedule_id=schedule.schedule_id,
            site=schedule.site,
            model=schedule.model,
            n_splits=schedule.n_splits,
            gap=schedule.gap,
            test_size=schedule.test_size,
            active=schedule.active,
            trigger_time=schedule.trigger_time.isoformat(timespec="minutes"),
            timezone=schedule.timezone,
            last_triggered_at=schedule.last_triggered_at,
        )

    @router.get("/schedules", response_model=list[ScheduleResponse])
    async def list_schedules() -> list[ScheduleResponse]:
        schedules = await manager.list_schedules()
        return [
            ScheduleResponse(
                schedule_id=s.schedule_id,
                site=s.site,
                model=s.model,
                n_splits=s.n_splits,
                gap=s.gap,
                test_size=s.test_size,
                active=s.active,
                trigger_time=s.trigger_time.isoformat(timespec="minutes"),
                timezone=s.timezone,
                last_triggered_at=s.last_triggered_at,
            )
            for s in schedules
        ]

    @router.patch("/schedules/{schedule_id}/active", response_model=ScheduleResponse)
    async def set_schedule_active(
        schedule_id: str, payload: ScheduleActiveUpdateRequest
    ) -> ScheduleResponse:
        schedule = await manager.set_schedule_active(schedule_id, payload.active)
        return ScheduleResponse(
            schedule_id=schedule.schedule_id,
            site=schedule.site,
            model=schedule.model,
            n_splits=schedule.n_splits,
            gap=schedule.gap,
            test_size=schedule.test_size,
            active=schedule.active,
            trigger_time=schedule.trigger_time.isoformat(timespec="minutes"),
            timezone=schedule.timezone,
            last_triggered_at=schedule.last_triggered_at,
        )

    @router.delete("/schedules/{schedule_id}")
    async def delete_schedule(schedule_id: str) -> dict[str, str]:
        await manager.delete_schedule(schedule_id)
        return {"status": "deleted"}

    return router
