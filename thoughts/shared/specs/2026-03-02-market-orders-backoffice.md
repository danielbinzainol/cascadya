# Market Orders Backoffice Specification

## Executive Summary
Build a new backoffice for operations and data teams to explore, review, and validate market orders, then compare orders against market results. The product supports both day-ahead and intraday workflows, with explicit validation for day-ahead and visualization-only for intraday in v1. The solution targets fast onboarding (Vue frontend), strong operational reliability, and clear decision accountability.

## Problem Statement
The current module computes market orders, but there is no dedicated review and validation interface before execution, and no unified view to compare proposed orders, planning, past behavior, and resulting market allocations. This creates risk of low visibility on coherence, weak traceability of accept/reject decisions, and slower reaction when order-result gaps appear.

## Success Criteria
- Every day-ahead order set has a clear status before the noon Europe/Paris deadline: validated, rejected (with reason), or auto-default applied.
- Every non-zero order-vs-result delta is visually identifiable for day-ahead and intraday views.
- Every rejection is justified, attributable to a user, and handled within operational workflow.
- Responsible validators receive one reminder notification one hour before deadline according to configured channel preferences.
- System retains 3 years of historical data for comparison and analysis.

## User Personas
- Operations team member (validator or viewer): Reviews charts, validates/rejects day-ahead order sets, monitors results.
- Data team member (validator or viewer): Checks coherence against planning, past orders, and consumption data.
- Admin: Manages users, roles, plant-level default behavior, and global configuration.

## User Journey
### Day-Ahead Review and Decision
1. User logs into backoffice.
2. User selects mode: `Review Market Orders` or `Review Market Results`.
3. Dashboard highlights pending reviews/validations by plant, date, and horizon.
4. User selects plant/date/horizon.
5. Orders review view shows superimposed chart: production planning + market orders, with past/future shading (default visible window: 1 week).
6. Validator either:
- Validates order set, or
- Rejects order set and must provide reason.
7. System stores decision with plant, date, horizon, username, UTC timestamp, decision, optional rejection reason, and order-set identifier/hash.
8. If no manual decision before noon Europe/Paris, plant-level default decision is applied and alerts are sent (unless muted at plant config level).

### Day-Ahead Results Comparison
1. Around 13:00 Europe/Paris, day-ahead market results are pulled from API.
2. User opens `Review Market Results` for plant/date/horizon.
3. Chart displays planning + orders + results.
4. Any non-zero delta between orders and results is highlighted with filled difference areas.
5. No additional validation action is required at this stage.

### Intraday Monitoring (v1)
1. Intraday orders are sent to broker API per 15-minute timeslots (96 points/day).
2. Intraday results are streamed by broker WebSocket (potential high-frequency updates).
3. Backoffice provides visualization/comparison only for intraday in v1.
4. No per-order intraday validation workflow in v1.

## Functional Requirements
### Must Have (P0)
- Role-based access control with local users:
- Roles: `admin`, `validator`, `viewer`.
- Admin can assign per-plant responsible validator.
- User authentication and password reset via email verification link (no admin direct reset).
- Security defaults:
- Minimum 12-character password.
- Password hashing with bcrypt.
- Session timeout after 8 hours.
- Account lock after 5 failed login attempts.
- Day-ahead review workspace:
- Plant/date/horizon selection.
- Pending status indicators.
- Superimposed chart of planning and market orders.
- Past vs future visual shading.
- Decision workflow:
- Validate or reject (reject requires reason).
- Store only the current effective decision if changed later.
- Persist decision metadata including order-set identifier/hash.
- Deadline automation:
- Hard deadline at 12:00 Europe/Paris.
- Per-plant default fallback action when pending:
- Copy yesterday's orders, or
- Buy nothing, or
- Copy last week's orders.
- Auto-default triggers alert unless muted for plant.
- If a broker-side order error arrives after send, validator has 30-minute correction window.
- Results ingestion:
- Day-ahead results pull once daily around 13:00 Europe/Paris.
- Intraday results ingest via WebSocket stream.
- Comparison visualization:
- Display orders vs results with highlight for every non-zero delta.
- Data retention:
- Keep 3 years history for orders, results, planning, consumption, and decisions.
- Notifications:
- Send reminder 1 hour before deadline to responsible validator.
- Exactly one preferred channel per user (`email`, `Teams`, or `in-app`) or muted.
- If deadline missed and validation expected, send alert to all users.

Acceptance criteria (P0)
- Given a pending day-ahead set at 11:00 Europe/Paris, responsible validator receives one reminder on selected channel unless muted.
- Given rejection action, system blocks submission without a non-empty reason.
- Given no decision by 12:00 Europe/Paris, configured plant default is applied automatically.
- Given results available, chart highlights every non-zero order-result difference.
- Given a decision update, only latest decision is shown as effective current state.

### Should Have (P1)
- Dashboard summary cards by plant: pending, validated, rejected, auto-defaulted, and recent gap counts.
- Advanced filtering (date range, horizon, decision status, user).
- Quick links from alert notifications directly to relevant plant/date/horizon view.
- Configurable default chart window (1 day / 3 days / 1 week).

Acceptance criteria (P1)
- User can filter backlog to find all rejected sets in a date range.
- User can open a notification link and land on exact review context.

### Nice to Have (P2)
- Delta severity bands (small/medium/large) configurable per plant.
- Bulk export (CSV) of charted comparison windows.
- Lightweight anomaly annotations for intraday deltas.

Acceptance criteria (P2)
- Admin can export comparison data for external analysis.

## Technical Architecture
### Technology Choices
- Frontend: Vue 3 + TypeScript.
- Backend API: FastAPI (Python).
- Time-series storage: PostgreSQL + TimescaleDB.
- Async/scheduled jobs: background worker for polling, deadlines, notifications.
- Hosting target: Scaleway cloud.

Rationale
- Vue selected for faster onboarding with equivalent v1 output.
- FastAPI aligns with existing Python project and API integration needs.
- TimescaleDB supports long retention and efficient time-window analytics.

### Data Model
Core entities:
- `plants`: plant metadata, fallback decision, alert mute settings, responsible validator.
- `users`: identity, role, auth fields, notification preferences.
- `day_ahead_order_sets`: plant/date/horizon, generated_at, source, hash/version, payload reference.
- `day_ahead_decisions`: current effective decision for plant/date/horizon/order_set_hash.
- `day_ahead_results`: timeseries points from market API.
- `intraday_orders`: timeseries points sent to broker API.
- `intraday_results`: timeseries points from broker WebSocket.
- `planning_timeseries`: production planning points.
- `consumption_timeseries`: past and predicted consumption points.
- `notifications`: reminder/alert events and delivery status.

### System Components
- Ingestion component for CSV imports (planning, past consumption, historical orders as needed).
- Broker integration component:
- Send intraday orders to broker API.
- Receive intraday results via WebSocket.
- Pull day-ahead results daily.
- Decision engine:
- Enforces noon Europe/Paris deadline.
- Applies per-plant default when pending.
- Opens 30-minute correction window when broker error event indicates invalid orders.
- Backoffice API:
- Serves chart and decision data.
- Applies RBAC checks.
- Handles validation/rejection actions.
- Notification service:
- Reminder and escalation rules.
- Channel-specific delivery (email/Teams/in-app).

### Integrations
- Market broker API for order submission and day-ahead result retrieval.
- Broker WebSocket for intraday result stream.
- Email service for reset links and email notifications.
- Teams webhook/integration for Teams notifications.

### Security Model
- Local user auth for v1.
- Password reset through email verification workflow.
- RBAC: admin/validator/viewer permissions enforced server-side.
- Session management with expiration.
- Login attempt rate limiting and lockout policy.
- Sensitive secrets (API tokens, SMTP credentials) managed through environment/secret manager.

## Non-Functional Requirements
- Performance:
- Day-ahead chart queries return in <2 seconds for default 1-week view.
- Intraday stream ingestion tolerates bursty updates and persists with ordered timestamps.
- Scalability:
- Start at 1 plant and scale to 10 plants by 18 months without architecture rewrite.
- Reliability:
- 99.5% uptime target.
- Idempotent ingestion for repeated broker/day-ahead pulls where possible.
- Security:
- Defaults as specified for auth and sessions.
- Observability:
- Structured logs and metrics for ingestion, deadline jobs, notifications, and API errors.
- Data retention:
- 3 years of time-series and decision-related records.

## Out of Scope (v1)
- Intraday per-order manual validation workflow.
- Compliance program implementation (no explicit GDPR/SOC2 requirement in v1).
- Multi-tenant architecture across separate organizations.
- Advanced forecasting model changes (backoffice consumes model output, does not redesign model logic).

## Open Questions for Implementation
- Final broker auth mechanism for production (token vs username/password) and renewal strategy.
- Precise broker API contract for order submission acknowledgements, retries, and idempotency semantics.
- Exact semantics for "validation expected" flag per plant when deciding all-user escalation alerts.
- Whether to keep a separate immutable audit log even when only latest effective decision is retained in business tables.
- Frontend chart library final pick in Vue stack (ECharts vs Plotly).

## Appendix: Research Findings
A brief architecture tradeoff pass was executed (no deep external research loop), resulting in these recommendations:
- Vue is appropriate for onboarding speed while keeping equivalent v1 capability.
- FastAPI + TimescaleDB is the lowest-friction path given existing Python codebase and time-series needs.
- Separate day-ahead batch flow from intraday streaming flow to reduce operational coupling.
