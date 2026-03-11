# Responsibilities Map

<a id="scope"></a>
## Scope
This map covers all repository files excluding runtime cache artifacts (`__pycache__`, `.pyc`).

<a id="directory-map"></a>
## Directory and Module Responsibilities

### `main.py`
Responsibility:
- Application entry script. Initializes Tk root, instantiates the primary app controller, and starts Tk event loop.

Key public objects:
- `main()`: bootstrap function.

Key dependencies:
- Internal: `gui.app_window.FileQuickViewApp`
- External/stdlib: `tkinter`

Notable risks/tech debt:
- No CLI args or runtime flags; startup behavior is fixed.

Where in code:
- `main.py:1-10`

### `core/` directory
Responsibility:
- Houses filesystem operation helpers used by GUI controller.

Key public objects:
- `FileHandler` class (static methods).

Key dependencies:
- Stdlib: `os`, built-in `open`

Notable risks/tech debt:
- Thin abstraction; no path validation or atomic writes.

Where in code:
- `core/file_handler.py:1-31`

### `core/__init__.py`
Responsibility:
- Package marker for `core` namespace.

Key public objects:
- None.

Key dependencies:
- None.

Notable risks/tech debt:
- None significant.

Where in code:
- `core/__init__.py` (empty file)

### `core/file_handler.py`
Responsibility:
- Provides static helpers for reading, saving, and creating files/folders.

Key public objects:
- `FileHandler.read_file(file_path)`
- `FileHandler.save_file(file_path, content)`
- `FileHandler.create_file(file_path)`
- `FileHandler.create_folder(folder_path)`

Key dependencies:
- Stdlib: `os.path.exists`, `os.makedirs`, built-in `open`

Notable risks/tech debt:
- `read_file` with `errors='replace'` may silently alter non-UTF8 content.
- `save_file` overwrites file directly; no backup/temp file.
- TOCTOU race possible between `exists` check and create.

Where in code:
- `core/file_handler.py:3-31`

### `gui/` directory
Responsibility:
- UI controller and reusable text editor widgets.

Key public objects:
- `FileQuickViewApp`
- `EditorWithLineNumbers`
- `PythonHighlighter`

Key dependencies:
- Internal: `core.file_handler`, `gui.line_text`, `gui.syntax`
- Stdlib: `tkinter`, `os`, `re`, `keyword`

Notable risks/tech debt:
- Controller class mixes UI rendering, state management, and filesystem orchestration in one module.

Where in code:
- `gui/app_window.py:1-218`, `gui/line_text.py:1-75`, `gui/syntax.py:1-60`

### `gui/__init__.py`
Responsibility:
- Package marker for `gui` namespace.

Key public objects:
- None.

Key dependencies:
- None.

Notable risks/tech debt:
- None significant.

Where in code:
- `gui/__init__.py` (empty file)

### `gui/app_window.py`
Responsibility:
- Main GUI controller: builds layout, binds events, manages workspace/file state, and dispatches IO actions.

Key public objects:
- `FileQuickViewApp`
- Methods: `load_directory`, `sync_tree`, `fill_tree`, `on_folder_extend`, `action_new_file`, `action_new_folder`, `on_file_select`, `on_text_change`, `save_file`

Key dependencies:
- Internal: `FileHandler`, `EditorWithLineNumbers`
- Stdlib/Tk: `os`, `tkinter`, `ttk`, `filedialog`, `messagebox`, `simpledialog`

Notable risks/tech debt:
- Silent autosave-on-file-switch may surprise users.
- `PermissionError` in tree fill is swallowed without user feedback.
- Toolbar/menu/status strings show mojibake in source (encoding mismatch in literals).
- UI and domain actions are tightly coupled, making unit testing harder.

Where in code:
- `gui/app_window.py:7-218`

### `gui/line_text.py`
Responsibility:
- Composite editor widget with synchronized line-number gutter and change-event proxying.

Key public objects:
- `LineNumberCanvas`
- `CustomText`
- `EditorWithLineNumbers`

Key dependencies:
- Internal: `PythonHighlighter`
- Stdlib/Tk: `tkinter`

Notable risks/tech debt:
- Tcl command rename/proxy approach is powerful but can be brittle if widget lifecycle edge cases occur.

Where in code:
- `gui/line_text.py:4-75`

### `gui/syntax.py`
Responsibility:
- Implements regex-based Python syntax highlighting with debounce and tag priority handling.

Key public objects:
- `PythonHighlighter`

Key dependencies:
- Stdlib: `re`, `keyword`
- Tk text-widget tag APIs via injected `text_widget`

Notable risks/tech debt:
- Regex parsing is lexical only and may mis-highlight complex Python constructs.
- Whole-buffer scans on highlight can be expensive for near-threshold file sizes.

Where in code:
- `gui/syntax.py:4-60`

<a id="cross-cutting"></a>
## Cross-Cutting Responsibility Notes
- State ownership is centralized in `FileQuickViewApp` (`current_file`, `current_workspace`, `is_dirty`, `is_loading`).
- Filesystem side effects are routed through `FileHandler`, except listing/checks which occur directly in GUI controller.
- No explicit abstraction boundary for domain model objects exists.

Where in code:
- State vars: `gui/app_window.py:13-16`
- Direct FS checks/listing: `gui/app_window.py:81`, `gui/app_window.py:134`, `gui/app_window.py:171`
- FS writes in handler: `core/file_handler.py:11-31`
