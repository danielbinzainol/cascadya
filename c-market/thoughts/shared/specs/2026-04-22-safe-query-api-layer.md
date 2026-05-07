# Safe Query API Layer Specification (MVP-First)

## Executive Summary
Implement the lightest in-app querying capability now: a simple SQL console in backoffice that accepts only single `SELECT`/`WITH` queries and blocks table modifications/deletions.  
Use this MVP for fast operational visibility, while keeping stronger controls (allowlists, advanced RBAC, exfiltration protections, deep audit) as later phases.

## Problem Statement
- We need to inspect data in the app database without using terminal.
- A web UI inside backoffice is preferred.
- For now, top priority is preventing data modification/deletion.
- Advanced governance concerns are acknowledged but intentionally deferred.

## Product Decision (Confirmed)
- **Now**: permissive read querying (all read SQL), strict block on write/DDL.
- **Later**: tighten with dataset/column allowlists, stricter role model, advanced safeguards.

## Scope (MVP)
- Add one query page in backoffice.
- Add one query endpoint:
  - accepts SQL text
  - validates read-only constraints
  - executes query and returns rows/columns
- Prevent writes/deletes using two layers:
  1. API-level validation (block dangerous keywords + multi-statement)
  2. DB transaction forced to `READ ONLY` during execution

## Out of Scope (MVP)
- Dataset/column allowlists
- Saved queries
- Query sharing
- BI dashboards
- Complex role matrix
- Cost controls beyond basic row limit + timeout

## API Contract (Implemented)

### Router
- File: `src/backoffice/api/routers/admin_queries.py`
- Prefix: `/admin/query`

### Endpoints
1. `GET /admin/query/tab`
- Returns query UI HTML.

2. `POST /admin/query/run`
- Request:
  - `sql: str`
  - `limit: int | null` (1..1000)
- Response:
  - `columns: list[str]`
  - `rows: list[dict[str, object]]`
  - `row_count: int`
  - `truncated: bool`
  - `limit: int`

## Query Validation Rules (Implemented)
- SQL must be non-empty.
- SQL must be a single statement.
- SQL must start with `SELECT` or `WITH`.
- Blocked keywords include:
  - `insert`, `update`, `delete`, `drop`, `alter`, `truncate`, `create`, `grant`, `revoke`, `comment`, `vacuum`, `analyze`, `refresh`, `call`, `do`, `copy`, `merge`
- If validation fails: HTTP 422.

## Runtime DB Safety (Implemented)
- Execute query inside explicit transaction.
- Apply `SET TRANSACTION READ ONLY` before query execution.
- Apply statement timeout (`BACKOFFICE_QUERY_TIMEOUT_MS`, default 15000ms).
- Apply row cap (`BACKOFFICE_QUERY_MAX_ROWS`, default 1000; default return 200).

## UI (Implemented)
- New page: `static/backoffice/query.html`
- Features:
  - SQL textarea
  - limit input
  - run button
  - results table
  - error display
- Added card link from `static/backoffice/index.html` to `/admin/query/tab`.

## Architecture
- `src/backoffice/services/query_service.py` handles validation + execution.
- `src/backoffice/persistence/database.py` now exposes `get_query_engine()`.
- Optional read-only URL for query endpoint:
  - `DATABASE_QUERY_URL` (preferred when available)
  - fallback: `DATABASE_URL` / computed DB URL

## Recommended DB Role (Next Ops Step)
For stronger guarantees, create a dedicated DB user for query endpoint with `SELECT` only:
- grant connect/usage/select
- deny insert/update/delete/truncate/ddl
- set `DATABASE_QUERY_URL` to this read-only user in deployment

## Deferred Concerns (Planned Later)
1. Data exfiltration risk reduction via allowlisted schema/views.
2. Expensive join/full scan protections (cost guardrails, query planner limits).
3. Sensitive column exposure controls.
4. Fine-grained authorization per dataset and per action.
5. Advanced audit model (who queried what, when, volume).
6. Feature flag + environment-based enablement for production.

## Acceptance Criteria (MVP)
- Backoffice exposes a query page reachable at `/admin/query/tab`.
- `POST /admin/query/run` executes valid read queries and returns tabular data.
- Write/delete/DDL queries are rejected.
- Multi-statement queries are rejected.
- Query execution path uses read-only transaction mode.
- Endpoint enforces timeout and row limit.
