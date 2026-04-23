# PRD (Actual State): file_viewer

<a id="document-status"></a>
## Document Status
- Basis: Static code inspection of repository contents only.
- Date: 2026-02-26
- Scope: Current implemented behavior; no aspirational features.

<a id="product-overview"></a>
## Product Overview (Observed)
`file_viewer` is a desktop GUI application for quickly browsing a local folder and editing text files in place. It combines a tree view of files/folders with a text editor that includes line numbers and Python-oriented syntax highlighting.

### Where in code
- App bootstrap: `main.py:4-10`
- Main app behavior: `gui/app_window.py:7-218`
- Editor composition: `gui/line_text.py:49-75`
- Syntax highlighter: `gui/syntax.py:4-60`

<a id="problem-statement"></a>
## Problem Statement (Inferred from Behavior)
The app reduces friction for local file inspection and quick edits by placing directory browsing, editing, and simple file/folder creation in one window.

### Where in code
- Open folder and tree sync: `gui/app_window.py:65-77`
- File selection and edit flow: `gui/app_window.py:165-218`
- New file/folder actions: `gui/app_window.py:138-160`

<a id="personas"></a>
## Personas / Users (Inferred)
- User editing local project/config/text files from desktop.
- User wanting lightweight Python-aware highlighting while editing.

Unknown:
- Formal target persona definitions are not present in repo.

### Inspected evidence
- Entire repository file list (only app code, no product docs/specs).

<a id="key-features"></a>
## Key Features (Observed)
1. Open a workspace folder via dialog (`Ctrl+O`) and populate tree.
2. Lazy-expand folders in tree to defer deep traversal.
3. Select file to load content into editor.
4. Auto-save current dirty file silently when switching files.
5. Save current file (`Ctrl+S` or button).
6. Create new file/folder from tree context menu.
7. Editor line numbers and Python syntax highlighting with debounce.
8. Status bar + window title indicate current state.

### Where in code
- Toolbar and shortcuts: `gui/app_window.py:21-34`
- Tree + lazy loading: `gui/app_window.py:42-50`, `gui/app_window.py:79-105`
- File open/autosave/save: `gui/app_window.py:165-218`
- Context menu create actions: `gui/app_window.py:109-160`
- Line numbers/change events: `gui/line_text.py:12-75`
- Highlighting: `gui/syntax.py:28-60`

<a id="non-goals"></a>
## Non-Goals / Not Present
- No remote filesystem support.
- No database integration.
- No authentication/authorization.
- No plugin architecture.
- No background worker or scheduled jobs.
- No HTTP API/web mode.
- No explicit rename/delete file operations.
- No tests/CI/lint/type-check tooling in repo.

### Where in code
- Local filesystem-only imports and operations: `core/file_handler.py:1-31`, `gui/app_window.py:1-5`, `gui/app_window.py:79-95`
- Repo inventory contains no CI/build/test config artifacts.

<a id="user-journeys"></a>
## User Journeys (Derived)
### Journey 1: Browse and edit a file
1. Launch app (`python main.py`).
2. Open folder via button or `Ctrl+O`.
3. Select file in tree.
4. Edit content.
5. Save via button or `Ctrl+S`.

### Where in code
- Launch: `main.py:4-10`
- Open folder: `gui/app_window.py:65-69`
- File select/load: `gui/app_window.py:165-194`
- Dirty tracking: `gui/app_window.py:196-201`
- Save: `gui/app_window.py:203-218`

### Journey 2: Create file/folder in workspace
1. Right-click tree item or empty area.
2. Choose New File or New Folder.
3. Enter name in dialog.
4. App creates item and refreshes tree.

### Where in code
- Context menu: `gui/app_window.py:109-125`
- Target directory selection: `gui/app_window.py:127-137`
- Create actions: `gui/app_window.py:138-160`
- Actual IO calls: `core/file_handler.py:17-31`

<a id="functional-requirements"></a>
## Functional Requirements (FR) from Current Implementation
- FR-01: System shall launch a Tkinter GUI main window.
  - Evidence: `main.py:4-7`
- FR-02: System shall allow selecting a workspace directory via native folder dialog.
  - Evidence: `gui/app_window.py:65-69`
- FR-03: System shall display directory tree sorted with folders first.
  - Evidence: `gui/app_window.py:81`
- FR-04: System shall exclude `__pycache__`, `__init__.py`, `.pyc` entries from tree display.
  - Evidence: `gui/app_window.py:83-84`
- FR-05: System shall lazy-load subfolders when expanded.
  - Evidence: `gui/app_window.py:92-104`
- FR-06: System shall read selected file content as UTF-8 with replacement for invalid bytes.
  - Evidence: `gui/app_window.py:178-181`, `core/file_handler.py:7-8`
- FR-07: System shall track dirty state after user edits loaded file.
  - Evidence: `gui/app_window.py:196-201`
- FR-08: System shall save current file as UTF-8.
  - Evidence: `gui/app_window.py:207-213`, `core/file_handler.py:13-14`
- FR-09: System shall auto-save prior dirty file on file switch.
  - Evidence: `gui/app_window.py:174-175`
- FR-10: System shall support creating new empty file and new folder.
  - Evidence: `gui/app_window.py:138-160`, `core/file_handler.py:17-31`
- FR-11: System shall show line numbers synced to visible lines.
  - Evidence: `gui/line_text.py:12-24`, `gui/line_text.py:67-68`
- FR-12: System shall apply Python syntax highlighting after debounced text changes.
  - Evidence: `gui/syntax.py:13`, `gui/syntax.py:28-60`

<a id="non-functional-requirements"></a>
## Non-Functional Requirements (Observed/Implied)
### Performance
- NFR-P1: Highlighting is skipped for files larger than 100000 chars to avoid UI freeze.
  - Evidence: `gui/syntax.py:37-38`
- NFR-P2: Folder traversal is lazy per node expansion, reducing initial tree load.
  - Evidence: `gui/app_window.py:92-104`

### Reliability
- NFR-R1: Permission errors during directory listing are swallowed (no crash, no warning).
  - Evidence: `gui/app_window.py:94-95`
- NFR-R2: File open/save/create errors are surfaced via message box.
  - Evidence: `gui/app_window.py:147-148`, `gui/app_window.py:159-160`, `gui/app_window.py:193-194`, `gui/app_window.py:215-216`

### Security & Privacy
- NFR-S1: No network transmission paths observed; operations are local.
  - Evidence: imports and methods across `main.py`, `core/file_handler.py`, `gui/*`
- NFR-S2: No secret management mechanism observed.
  - Evidence: repo has no config/secret handling modules.

### Observability
- NFR-O1: No structured logging, metrics, or tracing.
  - Evidence: no logging/telemetry libraries; status text only in GUI (`gui/app_window.py:58`, `gui/app_window.py:77`, `gui/app_window.py:146`, `gui/app_window.py:158`, `gui/app_window.py:187`, `gui/app_window.py:200`, `gui/app_window.py:212`)

<a id="constraints-assumptions"></a>
## Constraints & Assumptions
- Python with Tkinter support must be installed.
- User has local filesystem access rights to selected workspace.
- Text encoding for saves is always UTF-8.
- Intended file types are text; binary files will be lossy on read due to replacement behavior.

### Where in code
- Tkinter requirement: `main.py:1`, `gui/app_window.py:2-3`, `gui/line_text.py:1`
- File permissions assumptions: direct `open`/`os.listdir`/`os.makedirs` operations.
- UTF-8 behavior: `core/file_handler.py:7`, `core/file_handler.py:13`

<a id="open-questions"></a>
## Open Questions / Unknowns
- Unknown: Official product scope, target audience, and supported platforms.
  - Inspected: entire repo; no product docs.
- Unknown: Whether silent autosave-on-switch is intentional policy vs interim behavior.
  - Inspected: `gui/app_window.py:172-175` comment and implementation.
- Unknown: Expected behavior for binary files and huge files beyond highlighting skip.
  - Inspected: `core/file_handler.py:7`, `gui/syntax.py:37-38`.
- Unknown: Required testing quality gate and release process.
  - Inspected: repository has no tests/CI/release artifacts.

<a id="roadmap-suggestions"></a>
## Roadmap Suggestions (Not Current Behavior)
1. Add explicit prompt for unsaved changes instead of silent autosave.
2. Add rename/delete/search and optional Save As operations.
3. Add test suite for file operations and UI event logic.
4. Add basic logging + error diagnostics for permission and IO failures.
5. Add packaging metadata (`pyproject.toml`) and runnable entrypoint install.

These are recommendations only and are not implemented in current code.
