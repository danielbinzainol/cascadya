from __future__ import annotations

import tkinter as tk

from ui import theme
from ui.widgets import ScrollableFrame, create_badge, metric_card


class E2EPage(tk.Frame):
    def __init__(self, master: tk.Misc, app: "ControlPlaneApp") -> None:
        super().__init__(master, bg=theme.BG)
        self.app = app
        self.site_id = "ouest-consigne"
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.scroll = ScrollableFrame(self)
        self.scroll.grid(row=0, column=0, sticky="nsew")
        self.content = self.scroll.content
        self.content.grid_columnconfigure(0, weight=1)

    def set_site(self, site_id: str) -> None:
        self.site_id = site_id
        self.refresh()

    def refresh(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()

        site = self.app.state.sites[self.site_id]
        history = self.app.state.site_e2e_history.get(self.site_id, ())
        latest = history[0]

        tk.Label(
            self.content,
            text=f"Test E2E setpoint - {site.name}",
            bg=theme.BG,
            fg=theme.TEXT,
            font=("Segoe UI Semibold", 22),
        ).grid(row=0, column=0, sticky="w", pady=(6, 16))

        breadcrumb = tk.Frame(self.content, bg=theme.BG)
        breadcrumb.grid(row=1, column=0, sticky="w", pady=(0, 18))
        hop_labels = ("control plane", "ems-core", "ems-site", "modbus", "ems-light", "rte ack")
        hop_latencies = (12, 180, 95, 210, 305)
        for index, item in enumerate(hop_labels):
            badge = create_badge(breadcrumb, item, "running" if index == 0 else "waiting")
            badge.grid(row=0 if index < 5 else 1, column=index if index < 5 else 0, padx=(0, 10), pady=(0, 6), sticky="w")
            if index < 5:
                tk.Label(
                    breadcrumb,
                    text=f"-> {hop_latencies[index]}ms ->",
                    bg=theme.BG,
                    fg=theme.MUTED,
                    font=("Cascadia Mono", 10),
                ).grid(row=0, column=index * 2 + 1, sticky="w")

        metrics = tk.Frame(self.content, bg=theme.BG)
        metrics.grid(row=2, column=0, sticky="ew", pady=(12, 28))
        for index in range(4):
            metrics.grid_columnconfigure(index, weight=1)

        cards = (
            ("Round-trip total", f"{latest.total_ms} ms", "SLA: < 2 000 ms"),
            ("Hop le plus lent", f"{latest.light_rte} ms", "ems-light -> rte ack"),
            ("Dernier test", "10:06 UTC", "il y a 4 min"),
            ("Tendance 24h", "stable", "p95: 920 ms"),
        )
        for index, card in enumerate(cards):
            widget = metric_card(metrics, *card)
            widget.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 12, 0))

        tk.Label(
            self.content,
            text="Waterfall des hops",
            bg=theme.BG,
            fg=theme.TEXT,
            font=("Segoe UI Semibold", 18),
        ).grid(row=3, column=0, sticky="w", pady=(0, 18))

        waterfall = tk.Frame(self.content, bg=theme.BG)
        waterfall.grid(row=4, column=0, sticky="ew")
        labels = (
            ("CP -> NATS", latest.cp_core, theme.BLUE_DEEP),
            ("NATS -> ems-core", 45, theme.BLUE_DEEP),
            ("ems-core -> ems-site", latest.core_site, theme.BLUE_DEEP),
            ("ems-site -> modbus write", latest.modbus, theme.GREEN_BG),
            ("ems-site -> ems-light (ack)", latest.site_light, theme.BLUE_DEEP),
            ("ems-light -> rte ack", latest.light_rte, theme.AMBER_BG),
        )
        canvas = tk.Canvas(waterfall, width=1320, height=430, bg=theme.BG, highlightthickness=0, bd=0)
        canvas.pack(fill="x")
        x_origin = 320
        px_per_ms = 0.42
        for index, (label, duration, color) in enumerate(labels):
            y = 40 + index * 70
            canvas.create_text(70, y + 15, text=label, anchor="start", fill=theme.TEXT, font=("Segoe UI Semibold", 12))
            x = x_origin + sum(item[1] for item in labels[:index]) * px_per_ms
            width = duration * px_per_ms
            canvas.create_rectangle(x, y, x + width, y + 38, fill=color, width=0)
            canvas.create_text(x + width + 14, y + 19, text=f"{duration}ms", anchor="start", fill=theme.TEXT, font=("Cascadia Mono", 11))
        canvas.create_line(x_origin, 390, 1260, 390, fill=theme.WHITE_LINE)
        for tick in range(0, 2501, 500):
            x = x_origin + tick * px_per_ms
            canvas.create_text(x, 410, text=f"{tick}ms", fill=theme.MUTED, font=("Cascadia Mono", 10))
        canvas.create_text(1070, 40, text="SLA\n2s", fill=theme.RED, font=("Segoe UI Semibold", 12))

        header = tk.Frame(self.content, bg=theme.BG)
        header.grid(row=5, column=0, sticky="ew", pady=(36, 14))
        header.grid_columnconfigure(0, weight=1)
        tk.Label(
            header,
            text="Historique des tests (7 derniers jours)",
            bg=theme.BG,
            fg=theme.TEXT,
            font=("Segoe UI Semibold", 18),
        ).grid(row=0, column=0, sticky="w")
        tk.Button(
            header,
            text="Lancer un test",
            command=lambda: None,
            bg=theme.BG,
            fg=theme.TEXT,
            activebackground="#141414",
            activeforeground=theme.TEXT,
            relief="solid",
            bd=1,
            padx=26,
            pady=12,
            font=("Segoe UI Semibold", 12),
            cursor="hand2",
        ).grid(row=0, column=1, sticky="e")

        table = tk.Frame(self.content, bg=theme.BG)
        table.grid(row=6, column=0, sticky="ew")
        headers = (
            "Date",
            "Total",
            "CP->core",
            "core->site",
            "Modbus",
            "site->light",
            "light->rte",
            "Sparkline 7j",
            "Statut",
        )
        widths = (14, 12, 12, 12, 10, 12, 12, 16, 12)
        for index, (header_text, width) in enumerate(zip(headers, widths)):
            tk.Label(
                table,
                text=header_text,
                bg=theme.BG,
                fg=theme.MUTED,
                font=("Segoe UI Semibold", 11),
                width=width,
                anchor="w",
            ).grid(row=0, column=index, sticky="w", padx=8, pady=(0, 10))
        for row_index, row in enumerate(history, start=1):
            self._history_row(table, row_index, row)

    def _history_row(self, parent: tk.Widget, row_index: int, row) -> None:
        values = (
            row.date_label,
            f"{row.total_ms} ms",
            row.cp_core,
            row.core_site,
            row.modbus,
            row.site_light,
            row.light_rte,
        )
        widths = (14, 12, 12, 12, 10, 12, 12)
        for column_index, (value, width) in enumerate(zip(values, widths)):
            tk.Label(
                parent,
                text=value,
                bg=theme.BG,
                fg=theme.TEXT if column_index != 1 or row.status == "pass" else theme.AMBER,
                font=("Cascadia Mono", 11),
                width=width,
                anchor="w",
            ).grid(row=row_index * 2 - 1, column=column_index, sticky="w", padx=8, pady=10)

        spark = tk.Canvas(parent, width=160, height=34, bg=theme.BG, highlightthickness=0, bd=0)
        spark.grid(row=row_index * 2 - 1, column=7, sticky="w", padx=8)
        for index, value in enumerate(row.sparkline):
            x = index * 18 + 6
            height = 8 + value * 2
            color = theme.GREEN if row.status == "pass" else theme.AMBER
            spark.create_rectangle(x, 32 - height, x + 10, 32, fill=color, width=0)

        create_badge(parent, row.status, row.status).grid(row=row_index * 2 - 1, column=8, sticky="w", padx=8)
        tk.Frame(parent, bg=theme.WHITE_LINE, height=1).grid(row=row_index * 2, column=0, columnspan=9, sticky="ew")
