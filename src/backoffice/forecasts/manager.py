from __future__ import annotations

import asyncio
import csv
import io
import traceback
import uuid
from collections import defaultdict, deque
from datetime import datetime, time
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.backoffice.forecasts.models import (
    PARIS_TZ,
    ForecastRun,
    ForecastSchedule,
    _compute_single_model,
    _discover_sites,
    _json_safe,
    _load_site_timeseries_from_workflow,
    _now_utc,
    logger,
)
from src.backoffice.forecasts.scheduler import (
    _last_triggered_date_in_tz,
    _should_trigger_schedule,
)
from src.backoffice.forecasts.schemas import (
    RUN_STATUSES,
    RunCreateRequest,
    ScheduleCreateRequest,
    ScheduleUpdateRequest,
)
from src.backoffice.persistence.database import SessionLocal
from src.backoffice.persistence.models import (
    ForecastScheduleORM,
    InarizSteamForecast,
    InarizSteamProd,
)


class ForecastManager:
    def __init__(
        self,
        data_root: Path,
        *,
        now_utc_fn=None,
        discover_sites_fn=None,
        load_site_timeseries_from_workflow_fn=None,
        compute_single_model_fn=None,
        json_safe_fn=None,
    ) -> None:
        self._data_root = data_root
        self._runs: dict[str, ForecastRun] = {}
        self._schedules: dict[str, ForecastSchedule] = {}
        self._site_queue: dict[str, deque[str]] = defaultdict(deque)
        self._site_active: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._dispatcher_task: asyncio.Task | None = None
        self._scheduler_task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._now_utc = now_utc_fn or _now_utc
        self._discover_sites = discover_sites_fn or _discover_sites
        self._load_site_timeseries_from_workflow = (
            load_site_timeseries_from_workflow_fn or _load_site_timeseries_from_workflow
        )
        self._compute_single_model = compute_single_model_fn or _compute_single_model
        self._json_safe = json_safe_fn or _json_safe

    async def start(self) -> None:
        self._stop.clear()
        await asyncio.to_thread(self._bootstrap_timeseries_tables)
        schedules = await asyncio.to_thread(self._load_schedules_from_db)
        async with self._lock:
            self._schedules = {schedule.schedule_id: schedule for schedule in schedules}
        if self._dispatcher_task is None:
            self._dispatcher_task = asyncio.create_task(self._dispatcher_loop())
        if self._scheduler_task is None:
            self._scheduler_task = asyncio.create_task(self._scheduler_loop())

    async def stop(self) -> None:
        self._stop.set()
        for task in [self._dispatcher_task, self._scheduler_task]:
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._dispatcher_task = None
        self._scheduler_task = None

    async def create_run(
        self,
        payload: RunCreateRequest,
        trigger_source: Literal["manual", "scheduled"] = "manual",
    ) -> ForecastRun:
        logger.info(
            "enter create_run site=%s model=%s source=%s",
            payload.site,
            payload.model,
            trigger_source,
        )
        site = payload.site.lower().strip()
        if site not in self._discover_sites(self._data_root):
            raise HTTPException(
                status_code=404, detail=f"Unknown site '{payload.site}'."
            )
        run = ForecastRun(
            run_id=str(uuid.uuid4()),
            site=site,
            model=payload.model,
            n_splits=payload.n_splits,
            gap=payload.gap,
            test_size=payload.test_size,
            trigger_source=trigger_source,
            status="queued",
            created_at=self._now_utc(),
        )
        async with self._lock:
            self._runs[run.run_id] = run
            queue = self._site_queue[site]
            queue.append(run.run_id)
            self._recompute_queue_positions(site)
        return run

    async def list_runs(
        self, site: str | None = None, status: RUN_STATUSES | None = None
    ) -> list[ForecastRun]:
        logger.info("enter list_runs site=%s status=%s", site, status)
        async with self._lock:
            runs = list(self._runs.values())
        if site:
            runs = [r for r in runs if r.site == site.lower()]
        if status:
            runs = [r for r in runs if r.status == status]
        runs.sort(key=lambda r: r.created_at, reverse=True)
        return runs

    async def get_run(self, run_id: str) -> ForecastRun:
        logger.info("enter get_run run_id=%s", run_id)
        async with self._lock:
            run = self._runs.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"Unknown run '{run_id}'.")
        return run

    async def create_schedule(self, payload: ScheduleCreateRequest) -> ForecastSchedule:
        logger.info(
            "enter create_schedule site=%s model=%s", payload.site, payload.model
        )
        schedule = ForecastSchedule(
            schedule_id=str(uuid.uuid4()),
            site=payload.site.lower().strip(),
            model=payload.model,
            n_splits=payload.n_splits,
            gap=payload.gap,
            test_size=payload.test_size,
            active=payload.active,
            trigger_time=time(hour=9, minute=0),
            timezone="Europe/Paris",
        )
        if schedule.site not in self._discover_sites(self._data_root):
            raise HTTPException(
                status_code=404, detail=f"Unknown site '{payload.site}'."
            )
        schedule = await asyncio.to_thread(self._create_schedule_in_db, schedule)
        async with self._lock:
            self._schedules[schedule.schedule_id] = schedule
        return schedule

    async def update_schedule(
        self, schedule_id: str, payload: ScheduleUpdateRequest
    ) -> ForecastSchedule:
        logger.info("enter update_schedule schedule_id=%s", schedule_id)
        site = payload.site.lower().strip()
        if site not in self._discover_sites(self._data_root):
            raise HTTPException(
                status_code=404, detail=f"Unknown site '{payload.site}'."
            )
        schedule = await asyncio.to_thread(
            self._update_schedule_in_db, schedule_id, payload
        )
        async with self._lock:
            self._schedules[schedule_id] = schedule
        return schedule

    async def list_schedules(self) -> list[ForecastSchedule]:
        schedules = await asyncio.to_thread(self._load_schedules_from_db)
        async with self._lock:
            self._schedules = {schedule.schedule_id: schedule for schedule in schedules}
            values = list(self._schedules.values())
            values.sort(key=lambda s: s.schedule_id)
            return values

    async def set_schedule_active(
        self, schedule_id: str, active: bool
    ) -> ForecastSchedule:
        logger.info(
            "enter set_schedule_active schedule_id=%s active=%s", schedule_id, active
        )
        schedule = await asyncio.to_thread(
            self._set_schedule_active_in_db, schedule_id, active
        )
        async with self._lock:
            self._schedules[schedule_id] = schedule
        return schedule

    async def delete_schedule(self, schedule_id: str) -> None:
        logger.info("enter delete_schedule schedule_id=%s", schedule_id)
        await asyncio.to_thread(self._delete_schedule_in_db, schedule_id)
        async with self._lock:
            self._schedules.pop(schedule_id, None)

    def available_sites(self) -> list[str]:
        return self._discover_sites(self._data_root)

    async def _dispatcher_loop(self) -> None:
        logger.info("enter _dispatcher_loop")
        while not self._stop.is_set():
            await asyncio.sleep(0.3)
            launch_site: str | None = None
            launch_run: str | None = None
            async with self._lock:
                for site, queue in self._site_queue.items():
                    if not queue or site in self._site_active:
                        continue
                    launch_run = queue.popleft()
                    launch_site = site
                    self._site_active[site] = launch_run
                    self._recompute_queue_positions(site)
                    run = self._runs[launch_run]
                    run.status = "running"
                    run.started_at = self._now_utc()
                    break
            if launch_run is None or launch_site is None:
                continue
            asyncio.create_task(self._execute_run(launch_site, launch_run))

    async def _execute_run(self, site: str, run_id: str) -> None:
        logger.info("enter _execute_run site=%s run_id=%s", site, run_id)
        try:
            async with self._lock:
                run = self._runs[run_id]
            logger.info("_execute_run run_id=%s step=load_series", run_id)
            series = await asyncio.to_thread(self._load_site_timeseries, site)
            model_names = (
                ["simple_copy", "median_copy", "linear_regression"]
                if run.model == "all_models"
                else [run.model]
            )
            ranking: list[dict[str, float]] = []
            per_model: dict[str, dict[str, object]] = {}
            logs: list[str] = []
            for model_name in model_names:
                logs.append(f"Running model={model_name}")
                logger.info(
                    "_execute_run run_id=%s step=compute_model model=%s",
                    run_id,
                    model_name,
                )
                result = await asyncio.to_thread(
                    self._compute_single_model,
                    model_name,
                    series,
                    run.n_splits,
                    run.gap,
                    run.test_size,
                )
                per_model[model_name] = result
                metrics = result["metrics"]
                ranking.append({"model": model_name, "rmse": float(metrics["rmse"])})
            ranking.sort(key=lambda r: r["rmse"])
            selected_model = (
                ranking[0]["model"] if run.model == "all_models" else run.model
            )
            best = per_model[selected_model]
            await asyncio.to_thread(
                self._persist_forecast_series,
                site,
                best["export_rows"],
            )
            scoring_details_map: dict[int, dict[str, object]] = {}
            for model_name, model_result in per_model.items():
                fold_details = model_result.get("fold_details", [])
                for row in fold_details:
                    fold_num = int(row["fold"])
                    if fold_num not in scoring_details_map:
                        scoring_details_map[fold_num] = {
                            "fold": fold_num,
                            "train_start": row["train_start"],
                            "train_end": row["train_end"],
                            "test_start": row["test_start"],
                            "test_end": row["test_end"],
                            "test_std": row["test_std"],
                            "model_rmse": {},
                        }
                    scoring_details_map[fold_num]["model_rmse"][model_name] = row[
                        "model_rmse"
                    ][model_name]
            scoring_details = [
                scoring_details_map[k] for k in sorted(scoring_details_map.keys())
            ]
            csv_content = io.StringIO()
            writer = csv.DictWriter(
                csv_content, fieldnames=["timestamp", "segment", "actual", "predicted"]
            )
            writer.writeheader()
            for row in best["export_rows"]:
                writer.writerow(row)
            async with self._lock:
                run = self._runs[run_id]
                run.status = "done"
                run.finished_at = self._now_utc()
                run.metrics = self._json_safe(best["metrics"])
                run.scoring_details = self._json_safe(scoring_details)
                run.in_sample_chart = self._json_safe(best["in_sample_chart"])
                run.out_of_sample_chart = self._json_safe(best["out_of_sample_chart"])
                run.residual_chart = self._json_safe(best["residual_chart"])
                run.ranking = self._json_safe(
                    ranking
                    if run.model == "all_models"
                    else [
                        {
                            "model": selected_model,
                            "rmse": float(best["metrics"]["rmse"]),
                        }
                    ]
                )
                run.logs = "\n".join(logs)
                run.csv_buffer = csv_content.getvalue()
            logger.info("_execute_run run_id=%s status=done", run_id)
        except Exception as exc:  # noqa: BLE001
            async with self._lock:
                run = self._runs[run_id]
                run.status = "failed"
                run.finished_at = self._now_utc()
                run.error = str(exc)
                run.logs = traceback.format_exc(limit=8)
            logger.exception(
                "_execute_run run_id=%s status=failed error=%s", run_id, exc
            )
        finally:
            async with self._lock:
                self._site_active.pop(site, None)

    async def _scheduler_loop(self) -> None:
        while not self._stop.is_set():
            await asyncio.sleep(20)
            now_local = datetime.now(PARIS_TZ)
            today = now_local.date()
            if not _should_trigger_schedule(now_local):
                continue
            async with self._lock:
                schedules = list(self._schedules.values())
            for schedule in schedules:
                if not schedule.active:
                    continue
                last_date = _last_triggered_date_in_tz(
                    schedule.last_triggered_at, PARIS_TZ
                )
                if last_date == today:
                    continue
                payload = RunCreateRequest(
                    site=schedule.site,
                    model=schedule.model,
                    n_splits=schedule.n_splits,
                    gap=schedule.gap,
                    test_size=schedule.test_size,
                )
                await self.create_run(payload, trigger_source="scheduled")
                async with self._lock:
                    schedule.last_triggered_at = self._now_utc()

    def _recompute_queue_positions(self, site: str) -> None:
        queue = self._site_queue[site]
        for idx, run_id in enumerate(queue, start=1):
            self._runs[run_id].queue_position = idx

    def _bootstrap_timeseries_tables(self) -> None:
        """Populate raw timeseries tables at startup if they are empty."""
        with SessionLocal() as db:
            existing = db.scalar(select(InarizSteamProd.measured_at_utc).limit(1))
            if existing is not None:
                return

            logger.info(
                "bootstrap inariz_steam_prod from workflow because table is empty"
            )
            frame = self._load_site_timeseries_from_workflow(self._data_root, "inariz")
            rows = [
                InarizSteamProd(
                    measured_at_utc=row.measured_at_utc.to_pydatetime()
                    if hasattr(row.measured_at_utc, "to_pydatetime")
                    else row.measured_at_utc,
                    steam_production_m3_h=float(row.target),
                )
                for row in frame.itertuples(index=False)
            ]
            if not rows:
                raise ValueError("Workflow produced no rows for inariz_steam_prod.")
            db.bulk_save_objects(rows)
            db.commit()
            logger.info("bootstrapped inariz_steam_prod rows=%s", len(rows))

    def _load_site_timeseries(self, site: str) -> pd.DataFrame:
        """Load run input series from database, with workflow fallback."""
        if site != "inariz":
            return self._load_site_timeseries_from_workflow(self._data_root, site)

        with SessionLocal() as db:
            records = db.scalars(
                select(InarizSteamProd).order_by(InarizSteamProd.measured_at_utc.asc())
            ).all()

        if not records:
            logger.info(
                "inariz_steam_prod empty, fallback to workflow for site=%s", site
            )
            return self._load_site_timeseries_from_workflow(self._data_root, site)

        out = pd.DataFrame(
            {
                "measured_at_utc": [r.measured_at_utc for r in records],
                "target": [float(r.steam_production_m3_h) for r in records],
            }
        )
        out["measured_at_utc"] = pd.to_datetime(out["measured_at_utc"], utc=True)
        out = out.sort_values("measured_at_utc").reset_index(drop=True)
        if len(out) < 200:
            raise ValueError("Not enough history points to run cross-validation.")
        return out

    def _persist_forecast_series(
        self, site: str, export_rows: list[dict[str, object]]
    ) -> None:
        """Persist non-zero prediction rows used by In-Sample + Out-of-Sample chart."""
        if site != "inariz":
            return

        rows: list[dict[str, object]] = []
        for row in export_rows:
            segment = str(row.get("segment", ""))
            if segment not in {"in_sample_window", "out_of_sample"}:
                continue
            predicted = row.get("predicted")
            if predicted is None:
                continue
            predicted_value = float(predicted)
            ts = pd.to_datetime(row.get("timestamp"), errors="coerce", utc=True)
            if pd.isna(ts):
                continue
            rows.append(
                {
                    "measured_at_utc": ts.to_pydatetime(),
                    "steam_production_m3_h": predicted_value,
                    "unit": "m3/h",
                }
            )

        if not rows:
            logger.info("no forecast rows to persist for site=%s", site)
            return

        with SessionLocal() as db:
            stmt = pg_insert(InarizSteamForecast).values(rows)
            upsert = stmt.on_conflict_do_update(
                index_elements=[InarizSteamForecast.measured_at_utc],
                set_={
                    "steam_production_m3_h": stmt.excluded.steam_production_m3_h,
                    "unit": stmt.excluded.unit,
                },
            )
            db.execute(upsert)
            db.commit()
        logger.info("persisted forecast rows=%s site=%s", len(rows), site)

    def _load_schedules_from_db(self) -> list[ForecastSchedule]:
        with SessionLocal() as db:
            rows = db.scalars(
                select(ForecastScheduleORM).order_by(
                    ForecastScheduleORM.schedule_id.asc()
                )
            ).all()
        return [row.to_domain_schedule() for row in rows]

    def _create_schedule_in_db(self, schedule: ForecastSchedule) -> ForecastSchedule:
        with SessionLocal() as db:
            orm_schedule = ForecastScheduleORM(
                schedule_id=schedule.schedule_id,
                site=schedule.site,
                model=schedule.model,
                n_splits=schedule.n_splits,
                gap=schedule.gap,
                test_size=schedule.test_size,
                active=schedule.active,
                trigger_time=schedule.trigger_time,
                timezone=schedule.timezone,
                last_triggered_at=schedule.last_triggered_at,
            )
            db.add(orm_schedule)
            db.commit()
            db.refresh(orm_schedule)
            return orm_schedule.to_domain_schedule()

    def _update_schedule_in_db(
        self, schedule_id: str, payload: ScheduleUpdateRequest
    ) -> ForecastSchedule:
        with SessionLocal() as db:
            orm_schedule = db.get(ForecastScheduleORM, schedule_id)
            if orm_schedule is None:
                raise HTTPException(
                    status_code=404, detail=f"Unknown schedule '{schedule_id}'."
                )
            orm_schedule.site = payload.site.lower().strip()
            orm_schedule.model = payload.model
            orm_schedule.n_splits = payload.n_splits
            orm_schedule.gap = payload.gap
            orm_schedule.test_size = payload.test_size
            orm_schedule.active = payload.active
            db.commit()
            db.refresh(orm_schedule)
            return orm_schedule.to_domain_schedule()

    def _set_schedule_active_in_db(
        self, schedule_id: str, active: bool
    ) -> ForecastSchedule:
        with SessionLocal() as db:
            orm_schedule = db.get(ForecastScheduleORM, schedule_id)
            if orm_schedule is None:
                raise HTTPException(
                    status_code=404, detail=f"Unknown schedule '{schedule_id}'."
                )
            orm_schedule.active = active
            db.commit()
            db.refresh(orm_schedule)
            return orm_schedule.to_domain_schedule()

    def _delete_schedule_in_db(self, schedule_id: str) -> None:
        with SessionLocal() as db:
            orm_schedule = db.get(ForecastScheduleORM, schedule_id)
            if orm_schedule is None:
                raise HTTPException(
                    status_code=404, detail=f"Unknown schedule '{schedule_id}'."
                )
            db.delete(orm_schedule)
            db.commit()
