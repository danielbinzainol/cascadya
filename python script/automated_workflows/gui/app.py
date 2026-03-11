from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from gui.components import LogConsole
from gui.views.update_view import UpdateView
from utils.config import APP_GEOMETRY, APP_TITLE, MIN_WINDOW_SIZE


class CascadyaAdminApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(APP_GEOMETRY)
        self.minsize(*MIN_WINDOW_SIZE)
        self.configure(bg="#d8e1ea")

        self._configure_style()
        self._build_layout()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(".", font=("Segoe UI", 10))
        style.configure("TFrame", background="#d8e1ea")
        style.configure("TNotebook", background="#d8e1ea", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(18, 10), font=("Segoe UI Semibold", 10))
        style.map("TNotebook.Tab", background=[("selected", "#f7fbff")])

        style.configure(
            "Header.TFrame",
            background="#18354a",
        )
        style.configure(
            "HeaderTitle.TLabel",
            background="#18354a",
            foreground="#f7fbff",
            font=("Segoe UI Semibold", 20),
        )
        style.configure(
            "HeaderBody.TLabel",
            background="#18354a",
            foreground="#c7d5e0",
            font=("Segoe UI", 10),
        )
        style.configure(
            "ViewTitle.TLabel",
            background="#d8e1ea",
            foreground="#10212f",
            font=("Segoe UI Semibold", 16),
        )
        style.configure(
            "Card.TFrame",
            background="#f7fbff",
            relief="flat",
        )
        style.configure(
            "CardTitle.TLabel",
            background="#f7fbff",
            foreground="#10212f",
            font=("Segoe UI Semibold", 12),
        )
        style.configure(
            "CardBody.TLabel",
            background="#f7fbff",
            foreground="#4b6478",
        )
        style.configure(
            "Muted.TLabel",
            background="#d8e1ea",
            foreground="#4b6478",
        )
        style.configure(
            "TButton",
            padding=(14, 10),
            font=("Segoe UI Semibold", 10),
            background="#1f6f8b",
            foreground="#ffffff",
            borderwidth=0,
        )
        style.map(
            "TButton",
            background=[
                ("disabled", "#8da2b0"),
                ("pressed", "#184f63"),
                ("active", "#16586f"),
            ],
            foreground=[("disabled", "#e7edf2")],
        )

    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(2, weight=1)

        header = ttk.Frame(self, style="Header.TFrame", padding=(24, 18))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        title = ttk.Label(header, text=APP_TITLE, style="HeaderTitle.TLabel")
        title.grid(row=0, column=0, sticky="w")

        body = ttk.Label(
            header,
            text=(
                "Windows desktop GUI for WSL-based deployment, file synchronization "
                "and remote service management."
            ),
            style="HeaderBody.TLabel",
        )
        body.grid(row=1, column=0, sticky="w", pady=(4, 0))

        notebook = ttk.Notebook(self)
        notebook.grid(row=1, column=0, sticky="nsew", padx=20, pady=(20, 10))

        log_console = LogConsole(self)
        log_console.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 20))

        update_view = UpdateView(notebook, log_console=log_console)
        notebook.add(update_view, text="Updates")
