from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from .config import AppConfig
from .inventory import refresh_report
from .reporter import render_summary


class ServerCostApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Scaleway Cost Scanner")
        self.root.geometry("920x640")

        self.status_var = tk.StringVar(
            value="Ready. Fill .env, then click the refresh button."
        )

        container = ttk.Frame(self.root, padding=16)
        container.pack(fill="both", expand=True)

        title = ttk.Label(
            container,
            text="Scaleway Monthly Cost Scanner",
            font=("Segoe UI", 16, "bold"),
        )
        title.pack(anchor="w")

        subtitle = ttk.Label(
            container,
            text="One click refresh of servers, volumes, flexible IPs, and buckets.",
        )
        subtitle.pack(anchor="w", pady=(4, 12))

        controls = ttk.Frame(container)
        controls.pack(fill="x", pady=(0, 12))

        self.refresh_button = ttk.Button(
            controls,
            text="Refresh monthly estimate",
            command=self.start_refresh,
        )
        self.refresh_button.pack(side="left")

        self.status_label = ttk.Label(controls, textvariable=self.status_var)
        self.status_label.pack(side="left", padx=(12, 0))

        self.output = tk.Text(container, wrap="word", font=("Consolas", 10))
        self.output.pack(fill="both", expand=True)
        self.output.insert(
            "1.0",
            "The report summary will appear here after the first refresh.\n",
        )
        self.output.configure(state="disabled")

    def set_output(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", text)
        self.output.configure(state="disabled")

    def start_refresh(self) -> None:
        self.refresh_button.configure(state="disabled")
        self.status_var.set("Scanning Scaleway resources...")
        thread = threading.Thread(target=self._refresh_worker, daemon=True)
        thread.start()

    def _refresh_worker(self) -> None:
        try:
            config = AppConfig.from_env()
            result = refresh_report(config)
            summary = (
                render_summary(result.report)
                + "\n\n"
                + f"JSON report: {result.json_path}\n"
                + f"CSV report: {result.csv_path}\n"
                + f"Markdown report: {result.markdown_path}\n"
            )
            self.root.after(
                0,
                lambda summary_text=summary: self._refresh_done(
                    "Refresh completed.", summary_text, None
                ),
            )
        except Exception as exc:  # pragma: no cover
            error_message = str(exc)
            self.root.after(
                0,
                lambda message=error_message: self._refresh_done(
                    "Refresh failed.", None, message
                ),
            )

    def _refresh_done(
        self, status: str, summary: str | None, error_message: str | None
    ) -> None:
        self.status_var.set(status)
        self.refresh_button.configure(state="normal")
        if summary:
            self.set_output(summary)
        if error_message:
            self.set_output(error_message)
            messagebox.showerror("Scaleway Cost Scanner", error_message)

    def run(self) -> None:
        self.root.mainloop()


def launch_app() -> None:
    ServerCostApp().run()
