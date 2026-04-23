from __future__ import annotations

import os
import re
import time
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from workflows.base_workflow import BaseWorkflow


@dataclass(frozen=True)
class DashboardActionConfig:
    label: str
    trigger: Callable[[], None]
    enabled: bool = True
    primary: bool = False


@dataclass(frozen=True)
class DashboardStepConfig:
    key: str
    title: str
    category: str
    actual_titles: tuple[str, ...] = ()


DASHBOARD_STEPS = (
    DashboardStepConfig(
        key="sync",
        title="Synchronise WSL mirror",
        category="sync",
        actual_titles=("Synchronise WSL Mirror",),
    ),
    DashboardStepConfig(
        key="baseline",
        title="Collect baseline report",
        category="baseline",
        actual_titles=("Baseline Report",),
    ),
    DashboardStepConfig(
        key="certs",
        title="Generate remote unlock certificates",
        category="pki",
        actual_titles=("Generate Remote Unlock Certificates",),
    ),
    DashboardStepConfig(
        key="broker",
        title="Verify broker connectivity",
        category="broker",
        actual_titles=("Broker Connectivity Check",),
    ),
    DashboardStepConfig(
        key="vault",
        title="Seed Vault secret",
        category="vault",
        actual_titles=("Seed Vault Secret",),
    ),
    DashboardStepConfig(
        key="bootstrap",
        title="Bootstrap IPC + WireGuard",
        category="deploy",
        actual_titles=("Bootstrap IPC",),
    ),
    DashboardStepConfig(
        key="preflight",
        title="Run preflight checks",
        category="deploy",
        actual_titles=("Preflight",),
    ),
    DashboardStepConfig(
        key="validate",
        title="Validate broker unlock path",
        category="proof",
        actual_titles=("Validate",),
    ),
    DashboardStepConfig(
        key="cutover",
        title="Apply cutover",
        category="deploy",
        actual_titles=("Cutover",),
    ),
    DashboardStepConfig(
        key="reboot",
        title="Reboot fresh IPC + wait for reconnect",
        category="manual",
    ),
    DashboardStepConfig(
        key="proof",
        title="Run post-reboot proof",
        category="proof",
        actual_titles=("Post-Reboot Checks",),
    ),
)

STATUS_LABELS = {
    "idle": "ready",
    "running": "running",
    "awaiting_reboot": "awaiting reboot",
    "done": "done",
    "failed": "failed",
}

STEP_STATUS_LABELS = {
    "pending": "pending",
    "running": "running",
    "done": "done",
    "failed": "failed",
    "waiting": "will wait",
}

STEP_STATUS_COLORS = {
    "pending": ("#323232", "#a8a8a8"),
    "running": ("#314d73", "#9bc2ff"),
    "done": ("#214d17", "#82cf54"),
    "failed": ("#612626", "#ff9f95"),
    "waiting": ("#6d5614", "#e5c46a"),
}

JOB_STATUS_COLORS = {
    "idle": ("#2f2f33", "#c6ccd6"),
    "running": ("#314d73", "#9bc2ff"),
    "awaiting_reboot": ("#6d5614", "#e5c46a"),
    "done": ("#214d17", "#82cf54"),
    "failed": ("#612626", "#ff9f95"),
}

STEP_START_RE = re.compile(r"^\[step \d+/\d+\] (.+)$")
STEP_SUCCESS_RE = re.compile(r"^\[workflow\] Step '(.+)' completed successfully\.$")
STEP_WARNING_RE = re.compile(
    r"^\[workflow\] Step '(.+)' completed with tolerated warning exit code \d+\.$"
)
STEP_FAILURE_RE = re.compile(r"^\[workflow\] Stopped at step '(.+)' due to exit code \d+\.$")
OPERATOR_NAME = os.environ.get("USERNAME") or os.environ.get("USER") or "local operator"


class RemoteUnlockDashboard(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        primary_actions: tuple[DashboardActionConfig, ...],
        phase_actions: tuple[DashboardActionConfig, ...],
        **kwargs,
    ) -> None:
        super().__init__(master, bg="#050505", **kwargs)
        self._primary_actions = primary_actions
        self._phase_actions = phase_actions
        self._button_states: list[tuple[tk.Button, bool]] = []
        self._step_state = self._build_step_state()
        self._step_widgets: dict[str, dict[str, object]] = {}
        self._actual_title_to_key = {
            actual_title: config.key
            for config in DASHBOARD_STEPS
            for actual_title in config.actual_titles
        }
        self._job_status = "idle"
        self._job_id = "ru-idle"
        self._started_at: float | None = None
        self._running_tick = False
        self._status_var = tk.StringVar(value=STATUS_LABELS["idle"])
        self._title_var = tk.StringVar(value="Provisioning · Remote Unlock")
        self._meta_var = tk.StringVar(
            value="No provisioning job started yet. Run the full flow or pick a phase shortcut."
        )
        self._progress_var = tk.StringVar(value=f"0 / {len(DASHBOARD_STEPS)} steps completed")
        self._badge_label: tk.Label | None = None
        self._progress_canvas: tk.Canvas | None = None
        self._progress_fill: int | None = None

        self.grid_columnconfigure(0, weight=1)
        self._build_layout()
        self._refresh()

    def _build_layout(self) -> None:
        header = tk.Frame(self, bg="#050505")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title_row = tk.Frame(header, bg="#050505")
        title_row.grid(row=0, column=0, sticky="ew")
        title_row.grid_columnconfigure(0, weight=1)

        title = tk.Label(
            title_row,
            textvariable=self._title_var,
            bg="#050505",
            fg="#f4f1e8",
            font=("Segoe UI Semibold", 22),
            anchor="w",
        )
        title.grid(row=0, column=0, sticky="w")

        self._badge_label = tk.Label(
            title_row,
            textvariable=self._status_var,
            bg="#2f2f33",
            fg="#c6ccd6",
            font=("Segoe UI Semibold", 10),
            padx=16,
            pady=5,
        )
        self._badge_label.grid(row=0, column=1, sticky="e")

        meta = tk.Label(
            header,
            textvariable=self._meta_var,
            bg="#050505",
            fg="#cfc7b6",
            font=("Segoe UI", 11),
            anchor="w",
            justify="left",
        )
        meta.grid(row=1, column=0, sticky="w", pady=(10, 18))

        controls = tk.Frame(header, bg="#050505")
        controls.grid(row=2, column=0, sticky="ew")

        primary_row = tk.Frame(controls, bg="#050505")
        primary_row.grid(row=0, column=0, sticky="w")
        for index, action in enumerate(self._primary_actions):
            self._create_button(primary_row, action, row=0, column=index)

        reset_button = DashboardActionConfig(label="Reset State", trigger=self.reset, primary=False)
        self._create_button(primary_row, reset_button, row=0, column=len(self._primary_actions))

        shortcuts_label = tk.Label(
            controls,
            text="Phase shortcuts",
            bg="#050505",
            fg="#9f9a8d",
            font=("Consolas", 10),
            anchor="w",
        )
        shortcuts_label.grid(row=1, column=0, sticky="w", pady=(16, 8))

        shortcuts = tk.Frame(controls, bg="#050505")
        shortcuts.grid(row=2, column=0, sticky="ew")
        for index, action in enumerate(self._phase_actions):
            self._create_button(shortcuts, action, row=index // 4, column=index % 4)

        progress_frame = tk.Frame(self, bg="#050505")
        progress_frame.grid(row=1, column=0, sticky="ew", pady=(18, 22))
        progress_frame.grid_columnconfigure(0, weight=1)

        self._progress_canvas = tk.Canvas(
            progress_frame,
            height=12,
            bg="#050505",
            highlightthickness=0,
            bd=0,
        )
        self._progress_canvas.grid(row=0, column=0, sticky="ew")
        self._progress_canvas.bind("<Configure>", self._on_progress_resize)
        self._progress_fill = self._progress_canvas.create_rectangle(0, 0, 0, 12, fill="#8cb4e6", width=0)
        self._progress_canvas.create_rectangle(0, 0, 1, 12, outline="#d7d0c3", width=1, tags="outline")

        progress_label = tk.Label(
            progress_frame,
            textvariable=self._progress_var,
            bg="#050505",
            fg="#d6cec0",
            font=("Segoe UI Semibold", 10),
            anchor="w",
        )
        progress_label.grid(row=1, column=0, sticky="w", pady=(10, 0))

        self._step_shell = tk.Frame(
            self,
            bg="#050505",
            highlightbackground="#e0d7c9",
            highlightthickness=1,
            bd=0,
        )
        self._step_shell.grid(row=2, column=0, sticky="ew")
        self._step_shell.grid_columnconfigure(0, weight=1)

        for index, config in enumerate(DASHBOARD_STEPS):
            self._render_step_row(index, config)

    def _create_button(
        self,
        parent: tk.Widget,
        action: DashboardActionConfig,
        row: int,
        column: int,
    ) -> None:
        background = "#2f5f94" if action.primary else "#161616"
        active_background = "#284a70" if action.primary else "#242424"
        foreground = "#f4f1e8" if action.primary else "#ddd5c8"
        button = tk.Button(
            parent,
            text=action.label,
            command=action.trigger,
            bg=background,
            fg=foreground,
            activebackground=active_background,
            activeforeground="#ffffff",
            disabledforeground="#8e8a83",
            relief="flat",
            padx=14,
            pady=7,
            cursor="hand2",
            font=("Segoe UI Semibold", 10 if action.primary else 9),
            wraplength=180,
            justify="center",
        )
        button.grid(row=row, column=column, padx=(0, 10), pady=(0, 8), sticky="w")
        self._button_states.append((button, action.enabled))
        if not action.enabled:
            button.configure(state="disabled")

    def _render_step_row(self, row_index: int, config: DashboardStepConfig) -> None:
        container_row = row_index * 2
        row = tk.Frame(self._step_shell, bg="#050505", padx=18, pady=18)
        row.grid(row=container_row, column=0, sticky="ew")
        row.grid_columnconfigure(1, weight=1)

        icon = tk.Canvas(row, width=40, height=40, bg="#050505", highlightthickness=0, bd=0)
        icon.grid(row=0, column=0, sticky="w")
        circle = icon.create_oval(0, 0, 40, 40, fill="#323232", outline="")
        mark = icon.create_text(20, 20, text="", fill="#050505", font=("Segoe UI Semibold", 18))

        text_frame = tk.Frame(row, bg="#050505")
        text_frame.grid(row=0, column=1, sticky="w", padx=(16, 12))
        title = tk.Label(
            text_frame,
            text=config.title,
            bg="#050505",
            fg="#f4f1e8",
            font=("Segoe UI Semibold", 12),
            anchor="w",
        )
        title.grid(row=0, column=0, sticky="w")

        category = tk.Label(
            row,
            text=config.category,
            bg="#050505",
            fg="#9f9a8d",
            font=("Consolas", 10),
            anchor="e",
        )
        category.grid(row=0, column=2, sticky="e", padx=(0, 18))

        duration = tk.Label(
            row,
            text="",
            bg="#050505",
            fg="#d8d0c2",
            font=("Consolas", 10),
            width=8,
            anchor="e",
        )
        duration.grid(row=0, column=3, sticky="e", padx=(0, 18))

        status = tk.Label(
            row,
            text="pending",
            bg="#323232",
            fg="#a8a8a8",
            font=("Segoe UI Semibold", 10),
            padx=12,
            pady=4,
        )
        status.grid(row=0, column=4, sticky="e")

        self._step_widgets[config.key] = {
            "row": row,
            "icon": icon,
            "circle": circle,
            "mark": mark,
            "title": title,
            "category": category,
            "duration": duration,
            "status": status,
        }

        if row_index < len(DASHBOARD_STEPS) - 1:
            separator = tk.Frame(self._step_shell, bg="#e0d7c9", height=1)
            separator.grid(row=container_row + 1, column=0, sticky="ew")

    def _build_step_state(self) -> dict[str, dict[str, float | str | None]]:
        return {
            config.key: {
                "status": "pending",
                "started_at": None,
                "duration_seconds": None,
            }
            for config in DASHBOARD_STEPS
        }

    def reset(self) -> None:
        self._step_state = self._build_step_state()
        self._job_status = "idle"
        self._job_id = "ru-idle"
        self._started_at = None
        self._running_tick = False
        self._title_var.set("Provisioning · Remote Unlock")
        self._meta_var.set(
            "No provisioning job started yet. Run the full flow or pick a phase shortcut."
        )
        self._status_var.set(STATUS_LABELS["idle"])
        self._refresh()

    def set_enabled(self, enabled: bool) -> None:
        for button, default_enabled in self._button_states:
            button.configure(state="normal" if enabled and default_enabled else "disabled")

    def prepare_for_workflow(self, workflow: BaseWorkflow) -> None:
        workflow_name = workflow.__class__.__name__
        if workflow_name == "RemoteUnlockFullFlowWorkflow" or self._started_at is None:
            self._step_state = self._build_step_state()
            self._job_id = datetime.now().strftime("ru-%Y%m%d-%H%M%S")
            self._started_at = time.time()
        if workflow_name == "RemoteUnlockPostRebootProofWorkflow":
            self._set_step_status("reboot", "done")

        self._job_status = "running"
        self._status_var.set(STATUS_LABELS["running"])
        self._title_var.set("Provisioning · Remote Unlock")
        self._refresh()
        self._schedule_tick()

    def handle_log_message(self, message: str) -> None:
        match = STEP_START_RE.match(message)
        if match:
            self._start_step(match.group(1))
            return

        for pattern, status in (
            (STEP_SUCCESS_RE, "done"),
            (STEP_WARNING_RE, "done"),
            (STEP_FAILURE_RE, "failed"),
        ):
            match = pattern.match(message)
            if match:
                self._finish_step(match.group(1), status)
                return

    def finish_workflow(self, workflow: BaseWorkflow, succeeded: bool | None) -> None:
        workflow_name = workflow.__class__.__name__
        if not succeeded:
            self._job_status = "failed"
            self._status_var.set(STATUS_LABELS["failed"])
            self._refresh()
            return

        if workflow_name == "RemoteUnlockFullFlowWorkflow":
            self._set_step_status("reboot", "waiting")
            self._job_status = "awaiting_reboot"
            self._status_var.set(STATUS_LABELS["awaiting_reboot"])
        elif workflow_name == "RemoteUnlockPostRebootProofWorkflow":
            self._set_step_status("reboot", "done")
            self._job_status = "done"
            self._status_var.set(STATUS_LABELS["done"])
        else:
            if self._step_state["proof"]["status"] == "done":
                self._job_status = "done"
                self._status_var.set(STATUS_LABELS["done"])
            elif self._step_state["reboot"]["status"] == "waiting":
                self._job_status = "awaiting_reboot"
                self._status_var.set(STATUS_LABELS["awaiting_reboot"])
            else:
                self._job_status = "idle"
                self._status_var.set(STATUS_LABELS["idle"])

        self._refresh()

    def _schedule_tick(self) -> None:
        if self._running_tick:
            return
        self._running_tick = True
        self.after(1000, self._tick)

    def _tick(self) -> None:
        self._running_tick = False
        if self._job_status == "running":
            self._refresh()
            self._schedule_tick()

    def _start_step(self, actual_title: str) -> None:
        key = self._actual_title_to_key.get(actual_title)
        if key is None:
            return
        self._step_state[key]["status"] = "running"
        self._step_state[key]["started_at"] = time.perf_counter()
        self._step_state[key]["duration_seconds"] = None
        self._refresh()

    def _finish_step(self, actual_title: str, status: str) -> None:
        key = self._actual_title_to_key.get(actual_title)
        if key is None:
            return
        state = self._step_state[key]
        started_at = state["started_at"]
        state["status"] = status
        state["duration_seconds"] = (
            time.perf_counter() - float(started_at) if isinstance(started_at, (int, float)) else None
        )
        state["started_at"] = None
        self._refresh()

    def _set_step_status(self, key: str, status: str) -> None:
        state = self._step_state[key]
        state["status"] = status
        state["started_at"] = None

    def _refresh(self) -> None:
        self._apply_job_badge()
        self._update_meta()
        self._update_progress()
        self._refresh_steps()

    def _apply_job_badge(self) -> None:
        if self._badge_label is None:
            return
        bg, fg = JOB_STATUS_COLORS[self._job_status]
        self._badge_label.configure(bg=bg, fg=fg)

    def _update_meta(self) -> None:
        if self._started_at is None:
            return
        elapsed_seconds = max(0, int(time.time() - self._started_at))
        if elapsed_seconds < 60:
            elapsed = f"started {elapsed_seconds}s ago"
        else:
            elapsed = f"started {elapsed_seconds // 60} min ago"
        self._meta_var.set(f"Job {self._job_id} · triggered by {OPERATOR_NAME} · {elapsed}")

    def _update_progress(self) -> None:
        done_count = sum(1 for state in self._step_state.values() if state["status"] == "done")
        total = len(DASHBOARD_STEPS)
        self._progress_var.set(f"{done_count} / {total} steps completed")

        if self._progress_canvas is None or self._progress_fill is None:
            return
        width = max(self._progress_canvas.winfo_width(), 1)
        fill_width = width * (done_count / total if total else 0)
        self._progress_canvas.coords(self._progress_fill, 0, 0, fill_width, 12)
        self._progress_canvas.coords("outline", 0, 0, width, 12)

    def _refresh_steps(self) -> None:
        for config in DASHBOARD_STEPS:
            widgets = self._step_widgets.get(config.key)
            if not widgets:
                continue

            state = self._step_state[config.key]
            status_key = str(state["status"])
            row_bg = "#2f496d" if status_key == "running" else "#050505"
            text_fg = "#ffffff" if status_key == "running" else "#f4f1e8"
            muted_fg = "#d3cbbd" if status_key == "running" else "#9f9a8d"
            pill_bg, pill_fg = STEP_STATUS_COLORS[status_key]
            icon_fill = pill_fg if status_key == "done" else pill_bg
            icon_text = "✓" if status_key == "done" else ("↻" if status_key == "running" else "")

            row = widgets["row"]
            title = widgets["title"]
            category = widgets["category"]
            duration = widgets["duration"]
            status = widgets["status"]
            icon = widgets["icon"]
            circle = widgets["circle"]
            mark = widgets["mark"]

            row.configure(bg=row_bg)
            title.configure(bg=row_bg, fg=text_fg)
            category.configure(bg=row_bg, fg=muted_fg)
            duration.configure(bg=row_bg, fg=muted_fg)
            status.configure(text=STEP_STATUS_LABELS[status_key], bg=pill_bg, fg=pill_fg)
            icon.configure(bg=row_bg)
            icon.itemconfigure(circle, fill=icon_fill)
            icon.itemconfigure(mark, text=icon_text, fill="#09100b" if status_key == "done" else pill_fg)

            if status_key == "running" and isinstance(state["started_at"], (int, float)):
                duration.configure(text=f"{time.perf_counter() - float(state['started_at']):.1f}s")
            elif isinstance(state["duration_seconds"], (int, float)):
                duration.configure(text=f"{float(state['duration_seconds']):.1f}s")
            else:
                duration.configure(text="")

    def _on_progress_resize(self, _event: tk.Event) -> None:
        self._update_progress()
