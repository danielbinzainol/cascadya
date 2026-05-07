# Forecasts Backoffice Second Tab Specification

## Glossary
forecast run: one execution of train/test and forecast generation for one site and one chosen model (or all models mode)
all models mode: execution mode where all available models are run in the same settings and ranked by score
run ranking: ordered list of models for a run, sorted by ascending RMSE
schedule: recurring automated trigger that creates forecast runs

## Executive Summary
Build a second browser tab in the existing backoffice to launch forecasting runs, compare model performance, and visualize outputs for steam consumption. The tab targets operational visibility and model selection transparency, with both manual triggering and scheduled daily runs. V1 must run real training/testing workflows from existing repository methods and expose rich run diagnostics (metrics, charts, and technical traces).

## Problem Statement
The current project contains forecasting logic but lacks a unified operational interface to run, compare, and review model performance across sites in a consistent way. Users need a simple way to execute forecasting experiments on production-like settings, inspect in-sample/out-of-sample behavior, and keep historical evidence of model rankings over time.

## Success Criteria
- Users can launch real forecasting runs from the UI for one selected site.
- Users can run one model or all models in comparison mode.
- Every completed run displays mandatory outputs: metrics table, in-sample chart, out-of-sample chart, residual/error chart, and per-run CSV export.
- All-model runs store and display a persistent ranking by RMSE for historical comparison.
- Async job states are visible (`queued`, `running`, `done`, `failed`) with technical trace snippets on failure.
- A daily scheduled execution at 09:00 Europe/Paris can be configured in the tab and is visible in history.

## User Personas
- Internal backoffice users (all authenticated users): Launch runs, review results, compare models, inspect historical performance.
- Future automated operator (cron/scheduler): Executes configured recurring runs without manual interaction.

## User Journey
### Manual Run
1. User opens the Forecasts tab and sees an empty state requiring configuration.
2. User selects one site (for example `Inariz` or `Bout à bout`).
3. User selects one model or `All models`.
4. User enters `TimeSeriesSplit` parameters as free numeric inputs: `n_splits`, `gap`, `test_size`.
5. User launches the run.
6. Backend creates an async job and returns a run identifier.
7. UI shows job status (`queued` then `running` then terminal state).
8. If the site already has an active run, the new run is queued and queue position is visible.
9. On success, UI displays metrics and charts, and enables CSV export for that run.
10. On failure, UI displays user-readable error plus technical log/trace snippet.

### All Models Comparison
1. User selects `All models` and launches run.
2. Backend executes all configured models in identical data/split settings.
3. UI displays a ranking table sorted by RMSE (ascending).
4. Run history persists full ranking for later review.
5. V1 does not auto-activate the top model as a recommendation.

### Scheduled Runs
1. User creates or edits a schedule in tab UI.
2. V1 schedule cadence is daily at 09:00 Europe/Paris.
3. At trigger time, backend enqueues run(s) according to schedule configuration.
4. If previous run is still active for that site, next run is queued (not dropped), and this is visible in UI.

### Run History
1. User opens run history list.
2. User filters by site, model mode, date/time, and status.
3. User reopens a run to inspect metrics/charts/export and (for all-model runs) ranking table.

## Functional Requirements
### Must Have (P0)
- New backoffice tab dedicated to forecasting runs and review.
- Browser-accessible frontend aligned with existing backoffice deployment model (VM + Dockerized app).
- Site selector allowing exactly one site per run.
- Model selector supporting:
- `simple copy of past`
- `copy of median past values`
- `linear regression`
- `ARIMA`
- `LSTM`
- `All models` mode
- Data source for runs: latest ingested historical site data from backend storage (no UI CSV upload in v1).
- Fixed forecast horizon in v1: 24 hours.
- Fixed sampling interval in v1: 15 minutes.
- Configurable `TimeSeriesSplit` fields in UI as free numeric inputs:
- `n_splits`
- `gap`
- `test_size`
- Async execution model for all runs:
- states: `queued`, `running`, `done`, `failed`
- single active run per site at a time
- additional runs for same site are queued
- queue visibility in UI
- Run results view must include:
- metrics table (at least MAE, RMSE, MAPE, R2, train time)
- in-sample chart
- out-of-sample forecast chart
- residual/error chart
- CSV export per run
- All-model comparison behavior:
- compute ranking by RMSE (ascending)
- show ranking table
- persist ranking in run history
- no automatic adoption of best model output in v1
- Failure observability:
- user-facing failure state
- technical logs/trace snippet viewable from UI
- Run history page:
- list of past runs with filters (site, model/mode, datetime, status)
- ability to reopen each run results page
- Scheduling UI in v1:
- users can create/edit schedules
- cadence fixed to daily 09:00 Europe/Paris
- scheduled runs enqueue jobs with same async lifecycle

Acceptance criteria (P0)
- Given a run launch for a site without active run, status transitions from `queued` to `running` to `done` or `failed`.
- Given a second run launch while one run is `running` for the same site, the second appears as `queued` and is not lost.
- Given a successful run, metrics table and all three charts are displayed and CSV export is available.
- Given an all-model run, ranking table is displayed and persisted in history ordered by RMSE.
- Given a failed run, UI shows failure reason and technical trace snippet.
- Given schedule enabled, a run is enqueued every day at 09:00 Europe/Paris.

### Should Have (P1)
- Run configuration presets per site (save/reuse split parameters and model mode).
- Progress details for running jobs (current fold/model progress when available).
- Status badges and quick filters in run history for rapid triage.

Acceptance criteria (P1)
- User can launch a run using a saved preset without retyping parameters.
- User can distinguish queued vs running vs failed runs directly from list view.

### Nice to Have (P2)
- Side-by-side comparison charts across selected historical runs.
- Simple annotation field on a run (for example: "sensor issue period").
- Optional notification on run completion/failure.

Acceptance criteria (P2)
- User can add an annotation and retrieve it when reopening a historical run.

## Technical Architecture
### Technology Choices
- Frontend: Vue 3 + TypeScript (same as existing backoffice direction).
- Backend API: FastAPI (same project ecosystem).
- Forecast engine: existing `c_market` forecasting modules.
- Execution layer: async job queue/worker pattern for runs and scheduler triggers.
- Deployment: Dockerized services in VM, browser access through existing network setup.

### Data Model
Core entities:
- `forecast_runs`: run id, site, model mode, input parameters (`n_splits`, `gap`, `test_size`), trigger source (manual/scheduled), status, timestamps.
- `forecast_run_metrics`: per model/per fold and aggregated metrics (MAE, RMSE, MAPE, R2, train_time).
- `forecast_run_outputs`: references to in-sample/out-of-sample/residual series used by charts and CSV export payload.
- `forecast_run_rankings`: ordered model ranking for all-model runs (score metric = RMSE).
- `forecast_run_logs`: structured technical logs and trace snippets for failure/debug.
- `forecast_schedules`: site, model mode, parameters, active flag, daily trigger time (09:00 Europe/Paris).

### System Components
- Forecast run API:
- validate request payload
- create async job
- enforce per-site single-active-run rule
- Job worker:
- execute selected model(s)
- compute metrics and outputs
- persist run artifacts and status transitions
- Scheduler component:
- trigger daily jobs at 09:00 Europe/Paris
- enqueue if site already busy
- History/query API:
- list runs with filters
- retrieve run details, ranking, logs, chart payloads, and export data
- Frontend tab:
- configuration form
- run status tracking
- results and history visualizations

### Integrations
- Existing forecasting code in `src/` used by backend orchestration.
- Existing site/historical data ingestion and storage used as input source.
- Existing auth/session context from backoffice (no extra access restriction for this tab in v1).

### Security Model
- Reuse existing backoffice authentication/session policy.
- Forecast tab accessible to all authenticated users in v1.
- Log/trace visibility is available to all authenticated users in v1 (future hardening possible).

## Non-Functional Requirements
- Performance:
- API response for run submission returns quickly (<2s) with run id and status.
- Results retrieval should be responsive for recent runs (<2s target for standard payloads).
- Reliability:
- Job status transitions are durable and recoverable after service restart.
- Queued runs are not dropped on worker restart.
- Scalability:
- Single site initially, then multi-site operation with queue-based backpressure.
- Observability:
- Structured logs per run and per model.
- Trace snippet retained for failed runs.
- Timezone correctness:
- Scheduler and display use Europe/Paris semantics for 09:00 trigger, with explicit DST handling.

## Out of Scope (v1)
- Multi-site single-run execution in one click.
- User-uploaded dataset/CSV as forecast input.
- Editable sampling frequency or forecast horizon in UI.
- Automatic promotion of best model forecast as active recommendation.
- Side-by-side forecast overlay for all models (ranking table only).
- Advanced probabilistic composite score ranking (RMSE only in v1).

## Open Questions for Implementation
- Current repository implementation gap: ARIMA and LSTM pipelines are not yet production-implemented in `src/` and must be built before full v1 model list is operational.
- Confirm exact metric computation conventions for MAPE and R2 on edge cases (zeros, missing values, clipped values).
- Decide backend job framework details (native background tasks vs dedicated queue worker stack) while preserving durability requirements.
- Define retention policy for run artifacts (especially logs and chart series) to control storage growth.
- Decide whether technical trace snippets should later be role-restricted for security hardening.

## Appendix: Research Findings
Internal repository research was performed to align spec with current codebase:
- Forecast workflow already uses `TimeSeriesSplit` (`src/main.py`) with `n_splits` and `test_size`, confirming suitability of UI-exposed split parameters.
- Existing evaluation code computes MAE and RMSE in cross-validation (`src/evaluate.py`), consistent with RMSE-based ranking direction.
- Naive and median-copy forecasting utilities exist (`src/predict.py`).
- ARIMA and LSTM implementations are not yet operational in current repo state (`src/arima.py` is placeholder-only; no LSTM pipeline detected), so v1 delivery requires implementation work for those models.
