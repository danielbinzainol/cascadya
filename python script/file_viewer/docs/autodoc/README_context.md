# AI Context Pack: file_viewer

## 1) What this software is (observed)
`file_viewer` is a local desktop text-file explorer/editor built with Tkinter. It lets a user open a folder, browse a lazy-loaded file tree, open text files, edit them, save changes, and create new files/folders.

### Where in code
- App bootstrap and GUI main loop: `main.py:4-10`
- Main application controller: `gui/app_window.py:7-218`
- File operations (read/write/create): `core/file_handler.py:3-31`
- Editor widget + line numbers: `gui/line_text.py:4-75`
- Python syntax highlighting: `gui/syntax.py:4-60`

## 2) Architecture summary
- Presentation/UI: `FileQuickViewApp` builds toolbar, tree, editor, status bar and handles UI events.
- Editor subsystem: `EditorWithLineNumbers` (`CustomText` + `LineNumberCanvas`) emits `<<Change>>` for edits/scroll and drives redraw/highlighting.
- Domain/service layer (thin): `FileHandler` static methods perform file/folder IO.
- Integration boundary: local filesystem via `os`, `open`, `os.listdir`, `os.makedirs`.

No network clients, DB drivers, subprocess calls, or background worker frameworks were found.

### Where in code
- UI composition and event wiring: `gui/app_window.py:18-60`, `gui/app_window.py:109-125`
- Tree/file loading and lazy folder expansion: `gui/app_window.py:65-105`
- Save/load/create actions: `gui/app_window.py:138-160`, `gui/app_window.py:165-218`
- IO primitives: `core/file_handler.py:7-31`

## 3) Primary runtime flow
1. `python main.py` creates `tk.Tk()`, constructs `FileQuickViewApp`, enters `mainloop`.
2. User triggers Open Folder (`Ctrl+O`) and chooses a directory.
3. Tree is rebuilt from selected workspace (`sync_tree` -> `fill_tree`).
4. User selects a file; app optionally autosaves previous dirty file, reads selected file, updates editor and title.
5. User edits text; `<<Change>>` marks dirty state, updates title/status, redraws line numbers, schedules syntax highlight.
6. User saves (`Ctrl+S` or button); file content is written with UTF-8.

### Where in code
- Startup: `main.py:4-10`
- Open folder and sync: `gui/app_window.py:65-77`
- Tree population: `gui/app_window.py:79-95`, `gui/app_window.py:97-104`
- File open/autosave/read: `gui/app_window.py:165-194`
- Dirty tracking: `gui/app_window.py:196-201`
- Save: `gui/app_window.py:203-218`
- Highlight debounce and execution: `gui/syntax.py:28-60`

## 4) Domain glossary
- Workspace: root folder selected by user (`current_workspace`).
- Current file: currently opened file path (`current_file`).
- Dirty state: in-memory edits not yet saved (`is_dirty`).
- Loading guard: prevents dirty flag during programmatic editor updates (`is_loading`).
- Tree node lazy-expansion: folder nodes get a `dummy` child until expanded.

### Where in code
- State fields: `gui/app_window.py:13-16`
- Dirty/loading behavior: `gui/app_window.py:180-185`, `gui/app_window.py:196-201`
- Dummy-node lazy load: `gui/app_window.py:92-104`

## 5) Operational characteristics
- Runtime mode: GUI desktop app only.
- Dependencies: Python stdlib only (`tkinter`, `os`, `re`, `keyword`).
- Persistence: direct filesystem reads/writes in user-selected workspace.
- Encoding policy: read uses UTF-8 with `errors='replace'`; write uses UTF-8 strict.
- File filter in tree: hides `__pycache__`, `__init__.py`, and `.pyc` entries.
- Syntax highlighting guard: skipped for files >100000 chars.

### Where in code
- Imports/dependencies: `main.py:1-2`, `gui/app_window.py:1-5`, `gui/line_text.py:1-2`, `gui/syntax.py:1-2`
- Encoding behavior: `core/file_handler.py:7`, `core/file_handler.py:13`
- Tree filter: `gui/app_window.py:83-84`
- Highlight size guard: `gui/syntax.py:37-38`

## 6) Known limitations (observed)
- No explicit "Save As", rename, delete, search, tabs, undo/redo UI controls (undo exists at widget level only).
- No project config/env-var support.
- No automated tests, CI, packaging, lint/type-check config files found in repository.
- Toolbar/context-menu label text shows mojibake in source file encoding (icon strings are garbled in code text).

### Where in code
- Available actions are limited to open/sync/save/new file/new folder: `gui/app_window.py:31-34`, `gui/app_window.py:109-113`
- No non-code artifacts present in repo inventory: file listing from repository root (`main.py`, `core/*`, `gui/*`)
- Garbled button/menu strings: `gui/app_window.py:31-34`, `gui/app_window.py:111-112`, `gui/app_window.py:212`

## 7) Paste-ready short prompt for another AI agent
Use this codebase context:
- App type: local Tkinter file explorer/editor.
- Entrypoint: `python main.py`.
- Core class: `FileQuickViewApp` in `gui/app_window.py`.
- IO layer: `FileHandler` in `core/file_handler.py`.
- Editor widget: `EditorWithLineNumbers` + `PythonHighlighter`.
- Main state: `current_workspace`, `current_file`, `is_dirty`, `is_loading`.
- Key flows: open folder -> sync tree -> select file -> edit -> save; right-click tree -> create file/folder.
- Constraints: stdlib only, local filesystem only, no tests/CI/packaging configs currently.
- Unknowns requiring human confirmation: intended target users, supported OS matrix, desired file size/performance limits.
