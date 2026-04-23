# Unknowns and Gaps

<a id="purpose"></a>
## Purpose
This file lists items that could not be conclusively determined from code-only inspection, plus what was inspected to reach that conclusion.

<a id="unknowns"></a>
## Unknowns Requiring Human Confirmation

### 1) Product intent and audience
- Status: Unknown.
- Why unknown: No product docs, README, or issue history in repository.
- Inspected:
  - Entire repository tree (`main.py`, `core/*`, `gui/*`).

### 2) Supported OS / Python version policy
- Status: Partially known.
- Observed: Uses Tkinter APIs compatible with common CPython distributions.
- Unknown details: Minimum/maximum supported Python version and OS guarantees.
- Inspected:
  - `main.py:1-10`
  - `gui/app_window.py:1-218`
  - `gui/line_text.py:1-75`
  - `gui/syntax.py:1-60`

### 3) Autosave behavior policy
- Status: Unknown policy, behavior observed.
- Observed behavior: Dirty file is silently saved when switching to a different file.
- Unknown details: Whether this is intended UX requirement or temporary implementation.
- Inspected:
  - `gui/app_window.py:172-175`

### 4) Binary file handling expectations
- Status: Unknown policy, behavior observed.
- Observed behavior: reads with UTF-8 + replacement for decode issues; writes UTF-8.
- Risk: potential data corruption/loss for binary or non-UTF8 files.
- Inspected:
  - `core/file_handler.py:7-8`
  - `core/file_handler.py:13-14`

### 5) Large-file performance expectations
- Status: Partially known.
- Observed behavior: syntax highlighting disabled above 100000 chars.
- Unknown details: acceptable open/edit/save latency thresholds.
- Inspected:
  - `gui/syntax.py:37-38`

### 6) Security requirements
- Status: Unknown policy.
- Observed behavior: local-only file operations; no auth, no secret handling, no network logic.
- Unknown details: required hardening level (path restrictions, audit logging, sandboxing).
- Inspected:
  - `core/file_handler.py:1-31`
  - `gui/app_window.py:1-218`

### 7) Testing and release process
- Status: Unknown process; artifacts absent.
- Observed behavior: no tests, CI workflows, lint/type config, or packaging metadata in repo.
- Inspected:
  - Full file inventory from root and recursive listing.

### 8) Encoding anomalies in UI text literals
- Status: Behavior observed, root cause uncertain.
- Observed behavior: mojibake appears in button/menu/status literal strings in source.
- Unknown details: whether file encoding mismatch is in source control or local environment rendering.
- Inspected:
  - `gui/app_window.py:31-34`
  - `gui/app_window.py:111-113`
  - `gui/app_window.py:212`

<a id="gaps"></a>
## Gaps Between Current State and Typical Production Baseline
1. No automated test coverage.
2. No CI validation pipeline.
3. No packaging/distribution metadata.
4. No structured logging/telemetry.
5. No documented configuration contract.

These are not defects by themselves; they are absent capabilities relative to common production engineering baselines.
