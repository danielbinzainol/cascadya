from __future__ import annotations

import queue
import re
import time
import tkinter as tk
from datetime import datetime

from backend.remote_unlock import (
    PROVISION_STEP_ORDER,
    RemoteUnlockPostRebootWorkflow,
    RemoteUnlockPreRebootWorkflow,
)
from ui import theme
from ui.widgets import LogConsole, ScrollableFrame, create_badge, update_badge

STEP_START_RE = re.compile(r"^\[step \d+/\d+\] (.+)$")
STEP_SUCCESS_RE = re.compile(r"^\[workflow\] Step '(.+)' completed successfully\.$")
STEP_WARNING_RE = re.compile(
    r"^\[workflow\] Step '(.+)' completed with tolerated warning exit code \d+\.$"
)
STEP_FAILURE_RE = re.compile(r"^\[workflow\] Stopped at step '(.+)' due to exit code \d+\.$")
FATAL_LINE_RE = re.compile(r"(fatal:|failed!|traceback|not set|permission denied)", re.IGNORECASE)
OPERATOR = "operator.luc@cascadya.com"


class ProvisioningPage(tk.Frame):
    def __init__(self, master: tk.Misc, app: "ControlPlaneApp") -> None:
        super().__init__(master, bg=theme.BG)
        self.app = app
        self.site_id = "laiterie-bretagne"
        self.active_workflow = None
        self.message_queue: queue.Queue[str] = queue.Queue()
        self.job_status = "ready"
        self.job_id = "job-idle"
        self.job_started_at: float | None = None
        self.last_error = ""
        self.step_lookup = {
            actual_title: definition.key
            for definition in PROVISION_STEP_ORDER
            for actual_title in definition.actual_titles
        }
        self.step_state = self._build_step_state()
        self.step_widgets: dict[str, dict[str, object]] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.scroll = ScrollableFrame(self)
        self.scroll.grid(row=0, column=0, sticky="nsew")
        self.content = self.scroll.content
        self.content.grid_columnconfigure(0, weight=1)

        self.title_var = tk.StringVar()
        self.meta_var = tk.StringVar()
        self.progress_var = tk.StringVar()
        self.error_var = tk.StringVar()
        self._build()
        self.after(120, self._poll_messages)
        self.after(400, self._tick)

    def _build(self) -> None:
        breadcrumb = tk.Frame(self.content, bg=theme.BG)
        breadcrumb.grid(row=0, column=0, sticky="ew", pady=(6, 8))
        tk.Button(
            breadcrumb,
            text="Dashboard",
            command=self.app.show_dashboard,
            bg=theme.BG,
            fg=theme.BLUE,
            activebackground=theme.BG,
            activeforeground=theme.BLUE,
            relief="flat",
            bd=0,
            padx=0,
            font=("Segoe UI Semibold", 12),
            cursor="hand2",
        ).pack(side="left")
        tk.Label(
            breadcrumb,
            text=" / Jobs",
            bg=theme.BG,
            fg=theme.MUTED,
            font=("Segoe UI Semibold", 12),
        ).pack(side="left")

        head = tk.Frame(self.content, bg=theme.BG)
        head.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        head.grid_columnconfigure(0, weight=1)

        title_row = tk.Frame(head, bg=theme.BG)
        title_row.grid(row=0, column=0, sticky="w")
        tk.Label(
            title_row,
            textvariable=self.title_var,
            bg=theme.BG,
            fg=theme.TEXT,
            font=("Segoe UI Semibold", 24),
        ).grid(row=0, column=0, sticky="w")
        self.status_badge = create_badge(title_row, "ready", "ready")
        self.status_badge.grid(row=0, column=1, sticky="w", padx=(18, 0))

        tk.Label(
            head,
            textvariable=self.meta_var,
            bg=theme.BG,
            fg=theme.MUTED,
            font=("Segoe UI Semibold", 12),
        ).grid(row=1, column=0, sticky="w", pady=(10, 0))

        actions = tk.Frame(head, bg=theme.BG)
        actions.grid(row=0, column=1, rowspan=2, sticky="e")
        self.start_button = self._action_button(
            actions,
            "Run pre-reboot flow",
            self._start_pre_reboot_flow,
        )
        self.start_button.grid(row=0, column=0, padx=(0, 12))
        self.continue_button = self._action_button(
            actions,
            "Continue after reboot",
            self._start_post_reboot_flow,
        )
        self.continue_button.grid(row=0, column=1, padx=(0, 12))
        self.reset_button = self._action_button(actions, "Reset", self._reset)
        self.reset_button.grid(row=0, column=2, padx=(0, 12))
        self.back_button = self._action_button(
            actions,
            "Site view",
            lambda: self.app.show_site(self.site_id),
        )
        self.back_button.grid(row=0, column=3)

        self.error_banner = tk.Label(
            self.content,
            textvariable=self.error_var,
            bg=theme.RED_BG,
            fg=theme.RED,
            font=("Segoe UI Semibold", 11),
            padx=16,
            pady=10,
            anchor="w",
            justify="left",
        )

        progress_frame = tk.Frame(self.content, bg=theme.BG)
        progress_frame.grid(row=3, column=0, sticky="ew", pady=(8, 24))
        progress_frame.grid_columnconfigure(0, weight=1)
        self.progress_canvas = tk.Canvas(
            progress_frame,
            height=12,
            bg=theme.BG,
            highlightthickness=0,
            bd=0,
        )
        self.progress_canvas.grid(row=0, column=0, sticky="ew")
        self.progress_canvas.bind("<Configure>", lambda _event: self._refresh_progress())
        self.progress_fill = self.progress_canvas.create_rectangle(
            0,
            0,
            0,
            12,
            fill=theme.BLUE,
            width=0,
        )
        self.progress_canvas.create_rectangle(
            0,
            0,
            1,
            12,
            outline=theme.WHITE_LINE,
            width=1,
            tags="outline",
        )
        tk.Label(
            progress_frame,
            textvariable=self.progress_var,
            bg=theme.BG,
            fg=theme.MUTED,
            font=("Segoe UI Semibold", 12),
        ).grid(row=1, column=0, sticky="w", pady=(10, 0))

        step_shell = tk.Frame(
            self.content,
            bg=theme.BG,
            highlightbackground=theme.WHITE_LINE,
            highlightthickness=1,
            bd=0,
        )
        step_shell.grid(row=4, column=0, sticky="ew")
        step_shell.grid_columnconfigure(0, weight=1)
        self.step_shell = step_shell
        for index, definition in enumerate(PROVISION_STEP_ORDER):
            self._render_step_row(index, definition)

        self.console = LogConsole(
            self.content,
            highlightbackground=theme.PANEL,
            highlightthickness=1,
            bd=0,
        )
        self.console.grid(row=5, column=0, sticky="nsew", pady=(22, 0))
        self._reset()

    def set_site(self, site_id: str) -> None:
        self.site_id = site_id
        self.refresh()

    def refresh(self) -> None:
        site = self.app.state.sites[self.site_id]
        self.title_var.set(f"Provisioning - {site.name}")
        if self.job_started_at is None:
            self.meta_var.set(f"{site.city} ({site.code}) - {site.sector} - ready to run")

    def _action_button(self, parent: tk.Widget, label: str, command) -> tk.Button:
        return tk.Button(
            parent,
            text=label,
            command=command,
            bg=theme.BG,
            fg=theme.TEXT,
            activebackground="#141414",
            activeforeground=theme.TEXT,
            relief="solid",
            bd=1,
            padx=18,
            pady=10,
            font=("Segoe UI Semibold", 11),
            cursor="hand2",
        )

    def _render_step_row(self, index: int, definition) -> None:
        row = tk.Frame(self.step_shell, bg=theme.BG, padx=18, pady=18)
        row.grid(row=index * 2, column=0, sticky="ew")
        row.grid_columnconfigure(1, weight=1)

        icon = tk.Canvas(row, width=40, height=40, bg=theme.BG, highlightthickness=0, bd=0)
        icon.grid(row=0, column=0, sticky="w")
        circle = icon.create_oval(0, 0, 40, 40, fill=theme.GRAY_BG, outline="")
        mark = icon.create_text(20, 20, text="", fill=theme.BG, font=("Segoe UI Semibold", 10))

        title_label = tk.Label(
            row,
            text=definition.title,
            bg=theme.BG,
            fg=theme.TEXT,
            font=("Segoe UI Semibold", 15),
        )
        title_label.grid(row=0, column=1, sticky="w", padx=(16, 12))
        category_label = tk.Label(
            row,
            text=definition.category,
            bg=theme.BG,
            fg=theme.MUTED_2,
            font=("Cascadia Mono", 11),
        )
        category_label.grid(row=0, column=2, sticky="e", padx=(0, 18))
        duration = tk.Label(
            row,
            text="",
            bg=theme.BG,
            fg=theme.MUTED,
            font=("Cascadia Mono", 11),
            width=8,
            anchor="e",
        )
        duration.grid(row=0, column=3, sticky="e", padx=(0, 18))
        badge = create_badge(row, "pending", "pending")
        badge.grid(row=0, column=4, sticky="e")

        self.step_widgets[definition.key] = {
            "row": row,
            "icon": icon,
            "circle": circle,
            "mark": mark,
            "title": title_label,
            "category": category_label,
            "duration": duration,
            "badge": badge,
        }

        if index < len(PROVISION_STEP_ORDER) - 1:
            tk.Frame(self.step_shell, bg=theme.WHITE_LINE, height=1).grid(
                row=index * 2 + 1,
                column=0,
                sticky="ew",
            )

    def _build_step_state(self) -> dict[str, dict[str, object]]:
        return {
            definition.key: {
                "status": "pending",
                "started_at": None,
                "duration": None,
            }
            for definition in PROVISION_STEP_ORDER
        }

    def _reset(self) -> None:
        self.active_workflow = None
        self.job_status = "ready"
        self.job_id = "job-idle"
        self.job_started_at = None
        self.last_error = ""
        self.error_var.set("")
        self.error_banner.grid_forget()
        self.step_state = self._build_step_state()
        self.console.clear()
        self.refresh()
        self._apply_status()
        self._refresh_rows()
        self._refresh_progress()
        self._set_buttons(True)

    def _set_buttons(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.start_button.configure(state=state)
        self.continue_button.configure(state=state)
        self.reset_button.configure(state=state)

    def _start_pre_reboot_flow(self) -> None:
        self._start_workflow(RemoteUnlockPreRebootWorkflow())

    def _start_post_reboot_flow(self) -> None:
        self._start_workflow(RemoteUnlockPostRebootWorkflow())

    def _start_workflow(self, workflow) -> None:
        if self.active_workflow and self.active_workflow.is_running:
            return

        if isinstance(workflow, RemoteUnlockPreRebootWorkflow):
            self.console.clear()
            self.step_state = self._build_step_state()
            self.job_id = datetime.now().strftime("job-%Y%m%d-%H%M%S")
            self.job_started_at = time.time()
            self.last_error = ""
            self.error_var.set("")
            self.error_banner.grid_forget()
            self.app.on_provisioning_event(self.site_id, "started")
        else:
            if self.job_started_at is None:
                self.job_id = datetime.now().strftime("job-%Y%m%d-%H%M%S")
                self.job_started_at = time.time()
            if self.step_state["reboot"]["status"] == "will wait":
                self.step_state["reboot"]["status"] = "done"

        self.job_status = "running"
        self._apply_status()
        self._refresh_rows()
        self._refresh_progress()
        self._set_buttons(False)
        self.active_workflow = workflow
        workflow.run(self.message_queue.put)
        self.after(250, self._watch_workflow)

    def _watch_workflow(self) -> None:
        if self.active_workflow is None:
            return
        if self.active_workflow.is_running:
            self.after(250, self._watch_workflow)
            return

        workflow = self.active_workflow
        self.active_workflow = None
        if workflow.last_success:
            if isinstance(workflow, RemoteUnlockPreRebootWorkflow):
                self.step_state["reboot"]["status"] = "will wait"
                self.job_status = "awaiting reboot"
                self.app.on_provisioning_event(self.site_id, "awaiting_reboot")
                self.console.enqueue(
                    "[workflow] Pre-reboot flow finished. Reboot the IPC, wait for it to return, then click Continue after reboot."
                )
            else:
                self.job_status = "done"
                self.app.on_provisioning_event(self.site_id, "completed")
                self.console.enqueue("[workflow] Fresh IPC provisioning completed successfully.")
        else:
            self.job_status = "failed"
            self.app.on_provisioning_event(self.site_id, "failed")

        self._apply_status()
        self._refresh_rows()
        self._refresh_progress()
        self._set_buttons(True)

    def _poll_messages(self) -> None:
        while True:
            try:
                message = self.message_queue.get_nowait()
            except queue.Empty:
                break
            self.console.enqueue(message)
            self._handle_message(message)
        self.after(120, self._poll_messages)

    def _handle_message(self, message: str) -> None:
        if FATAL_LINE_RE.search(message):
            self._set_error(message)

        match = STEP_START_RE.match(message)
        if match:
            step_key = self.step_lookup.get(match.group(1))
            if step_key is None:
                return
            self.step_state[step_key]["status"] = "running"
            self.step_state[step_key]["started_at"] = time.perf_counter()
            self.step_state[step_key]["duration"] = None
            self._refresh_rows()
            self._refresh_progress()
            return

        match = STEP_SUCCESS_RE.match(message) or STEP_WARNING_RE.match(message)
        if match:
            step_key = self.step_lookup.get(match.group(1))
            if step_key is None:
                return
            self._complete_step(step_key, "done")
            return

        match = STEP_FAILURE_RE.match(message)
        if match:
            step_key = self.step_lookup.get(match.group(1))
            if step_key is None:
                self._set_error(message)
                return
            self._complete_step(step_key, "failed")
            self._set_error(message)

    def _complete_step(self, step_key: str, status: str) -> None:
        started_at = self.step_state[step_key]["started_at"]
        self.step_state[step_key]["status"] = status
        self.step_state[step_key]["duration"] = (
            time.perf_counter() - float(started_at) if started_at is not None else None
        )
        self.step_state[step_key]["started_at"] = None
        self._refresh_rows()
        self._refresh_progress()

    def _set_error(self, message: str) -> None:
        if message == self.last_error:
            return
        self.last_error = message
        clean_message = message.replace("[stderr] ", "")
        self.error_var.set(f"Error: {clean_message}")
        self.error_banner.grid(row=2, column=0, sticky="ew", pady=(0, 8))

    def _tick(self) -> None:
        if self.job_started_at is not None:
            elapsed = max(0, int(time.time() - self.job_started_at))
            if elapsed < 60:
                started_text = f"started {elapsed}s ago"
            else:
                started_text = f"started {elapsed // 60} min ago"
            self.meta_var.set(f"{self.job_id} - triggered by {OPERATOR} - {started_text}")
        self._refresh_rows()
        self.after(400, self._tick)

    def _apply_status(self) -> None:
        update_badge(self.status_badge, self.job_status, self.job_status)

    def _refresh_progress(self) -> None:
        completed = sum(1 for state in self.step_state.values() if state["status"] == "done")
        total = len(PROVISION_STEP_ORDER)
        self.progress_var.set(f"{completed} / {total} steps completed")
        width = max(self.progress_canvas.winfo_width(), 1)
        fill = width * (completed / total if total else 0)
        self.progress_canvas.coords(self.progress_fill, 0, 0, fill, 12)
        self.progress_canvas.coords("outline", 0, 0, width, 12)

    def _refresh_rows(self) -> None:
        for definition in PROVISION_STEP_ORDER:
            state = self.step_state[definition.key]
            widgets = self.step_widgets[definition.key]
            status = str(state["status"])
            row_bg = theme.BLUE_DEEP if status == "running" else theme.BG

            row = widgets["row"]
            icon = widgets["icon"]
            title_label = widgets["title"]
            category_label = widgets["category"]
            duration = widgets["duration"]
            badge = widgets["badge"]

            row.configure(bg=row_bg)
            icon.configure(bg=row_bg)
            title_label.configure(bg=row_bg)
            category_label.configure(bg=row_bg)
            duration.configure(bg=row_bg)

            fill, fg = theme.STATUS_STYLES.get(status, theme.STATUS_STYLES["pending"])
            icon_fill = fg if status == "done" else fill
            if status == "failed":
                icon_fill = theme.RED_BG
            icon.itemconfigure(widgets["circle"], fill=icon_fill)

            if status == "done":
                mark_text = "ok"
                mark_fill = theme.BG
            elif status == "running":
                mark_text = "..."
                mark_fill = fg
            elif status == "failed":
                mark_text = "!"
                mark_fill = theme.RED
            elif status == "will wait":
                mark_text = "..."
                mark_fill = fg
            else:
                mark_text = ""
                mark_fill = fg
            icon.itemconfigure(widgets["mark"], text=mark_text, fill=mark_fill)

            badge.configure(bg=fill, fg=fg, text=status)
            if status == "running" and state["started_at"] is not None:
                duration.configure(text=f"{time.perf_counter() - float(state['started_at']):.1f}s")
            elif state["duration"] is not None:
                duration.configure(text=f"{float(state['duration']):.1f}s")
            else:
                duration.configure(text="")
