from __future__ import annotations

import tkinter as tk

from ui import theme
from ui.widgets import ScrollableFrame, create_badge


class SitePage(tk.Frame):
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
        services = self.app.state.site_services.get(self.site_id, ())
        alerts = self.app.state.site_alerts.get(self.site_id, ())
        routes = self.app.state.site_routes.get(self.site_id, ())
        assets = self.app.state.site_assets.get(self.site_id, ())

        tk.Label(
            self.content,
            text=f"Dashboard / {site.name}",
            bg=theme.BG,
            fg=theme.BLUE,
            font=("Segoe UI Semibold", 13),
        ).grid(row=0, column=0, sticky="w", pady=(6, 16))

        head = tk.Frame(self.content, bg=theme.BG)
        head.grid(row=1, column=0, sticky="ew")
        head.grid_columnconfigure(0, weight=1)

        left = tk.Frame(head, bg=theme.BG)
        left.grid(row=0, column=0, sticky="w")
        title_row = tk.Frame(left, bg=theme.BG)
        title_row.grid(row=0, column=0, sticky="w")
        tk.Label(
            title_row,
            text=site.name,
            bg=theme.BG,
            fg=theme.TEXT,
            font=("Segoe UI Semibold", 24),
        ).grid(row=0, column=0, sticky="w")
        create_badge(title_row, site.status, site.status).grid(row=0, column=1, sticky="w", padx=(16, 0))
        tk.Label(
            left,
            text=f"{site.city} ({site.code}) - {site.sector} - {site.capacity_mw:.1f} MW aFRR",
            bg=theme.BG,
            fg=theme.MUTED,
            font=("Segoe UI Semibold", 14),
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))

        right = tk.Frame(head, bg=theme.BG)
        right.grid(row=0, column=1, sticky="e")
        self._action_button(right, "Test\nE2E", lambda: self.app.show_e2e(site.site_id)).grid(row=0, column=0, padx=(0, 14))
        self._action_button(right, "Jobs", lambda: self.app.show_provisioning(site.site_id)).grid(row=0, column=1)

        tk.Label(
            self.content,
            text="Services",
            bg=theme.BG,
            fg=theme.TEXT,
            font=("Segoe UI Semibold", 18),
        ).grid(row=2, column=0, sticky="w", pady=(36, 18))
        cards = tk.Frame(self.content, bg=theme.BG)
        cards.grid(row=3, column=0, sticky="ew")
        for index in range(3):
            cards.grid_columnconfigure(index, weight=1)
        for index, service in enumerate(services):
            self._service_card(cards, index, service.name, service.status, service.lines)

        tk.Label(
            self.content,
            text="Alertes actives",
            bg=theme.BG,
            fg=theme.TEXT,
            font=("Segoe UI Semibold", 18),
        ).grid(row=4, column=0, sticky="w", pady=(36, 18))
        for row_index, alert in enumerate(alerts, start=5):
            banner = tk.Frame(
                self.content,
                bg=theme.AMBER_BG,
                highlightbackground="#80651d",
                highlightthickness=1,
                bd=0,
            )
            banner.grid(row=row_index, column=0, sticky="ew", pady=(0, 14))
            tk.Label(
                banner,
                text="[!]",
                bg=theme.AMBER_BG,
                fg=theme.AMBER,
                font=("Segoe UI Semibold", 16),
            ).pack(side="left", padx=(20, 14), pady=18)
            tk.Label(
                banner,
                text=alert,
                bg=theme.AMBER_BG,
                fg=theme.AMBER,
                font=("Segoe UI", 14),
            ).pack(side="left", pady=20)
            tk.Label(
                banner,
                text="09:30 UTC",
                bg=theme.AMBER_BG,
                fg=theme.MUTED,
                font=("Segoe UI", 12),
            ).pack(side="right", padx=20, pady=20)

        routing_row = 5 + len(alerts)
        tk.Label(
            self.content,
            text="Table de routing NATS",
            bg=theme.BG,
            fg=theme.TEXT,
            font=("Segoe UI Semibold", 18),
        ).grid(row=routing_row, column=0, sticky="w", pady=(36, 14))
        routing = tk.Frame(self.content, bg=theme.BG)
        routing.grid(row=routing_row + 1, column=0, sticky="ew")
        headers = ("Route", "Subject", "Publisher", "Subscriber", "Rate", "Statut")
        widths = (24, 50, 18, 18, 10, 12)
        for column_index, (header, width) in enumerate(zip(headers, widths)):
            tk.Label(
                routing,
                text=header,
                bg=theme.BG,
                fg=theme.MUTED,
                font=("Segoe UI Semibold", 11),
                width=width,
                anchor="w",
            ).grid(row=0, column=column_index, sticky="w", padx=8, pady=(0, 10))
        for row_index, route in enumerate(routes, start=1):
            self._routing_row(routing, row_index, route)

        job_row = routing_row + 2
        tk.Label(
            self.content,
            text="Dernier job de provisioning",
            bg=theme.BG,
            fg=theme.TEXT,
            font=("Segoe UI Semibold", 18),
        ).grid(row=job_row, column=0, sticky="w", pady=(36, 14))
        job = tk.Frame(self.content, bg=theme.BG)
        job.grid(row=job_row + 1, column=0, sticky="ew")
        canvas = tk.Canvas(job, height=10, bg=theme.BG, highlightthickness=0, bd=0)
        canvas.pack(fill="x")
        canvas.create_rectangle(0, 0, 1320, 10, fill=theme.GREEN, width=0)
        tk.Label(
            job,
            text=site.last_job_summary,
            bg=theme.BG,
            fg=theme.TEXT,
            font=("Cascadia Mono", 12),
        ).pack(anchor="w", pady=(8, 0))

        asset_row = job_row + 2
        tk.Label(
            self.content,
            text="Assets",
            bg=theme.BG,
            fg=theme.TEXT,
            font=("Segoe UI Semibold", 18),
        ).grid(row=asset_row, column=0, sticky="w", pady=(36, 14))
        asset_table = tk.Frame(self.content, bg=theme.BG)
        asset_table.grid(row=asset_row + 1, column=0, sticky="ew")
        headers = ("Type", "Fabricant", "Modele", "Puissance", "Modbus")
        widths = (22, 20, 16, 14, 28)
        for column_index, (header, width) in enumerate(zip(headers, widths)):
            tk.Label(
                asset_table,
                text=header,
                bg=theme.BG,
                fg=theme.MUTED,
                font=("Segoe UI Semibold", 11),
                width=width,
                anchor="w",
            ).grid(row=0, column=column_index, sticky="w", padx=8, pady=(0, 10))
        for row_index, asset in enumerate(assets, start=1):
            self._asset_row(asset_table, row_index, asset)

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
            padx=24,
            pady=10,
            font=("Segoe UI Semibold", 12),
            cursor="hand2",
        )

    def _service_card(
        self,
        parent: tk.Widget,
        column: int,
        title: str,
        status: str,
        lines: tuple[str, ...],
    ) -> None:
        card = tk.Frame(
            parent,
            bg=theme.PANEL,
            highlightbackground=theme.BORDER,
            highlightthickness=1,
            bd=0,
        )
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 18, 0))
        card.grid_columnconfigure(0, weight=1)
        accent = tk.Frame(card, bg=theme.GREEN, width=5)
        accent.grid(row=0, column=0, rowspan=6, sticky="nsw")
        title_row = tk.Frame(card, bg=theme.PANEL)
        title_row.grid(row=0, column=1, sticky="ew", padx=28, pady=(24, 14))
        title_row.grid_columnconfigure(0, weight=1)
        tk.Label(
            title_row,
            text=title,
            bg=theme.PANEL,
            fg=theme.TEXT,
            font=("Segoe UI Semibold", 16),
        ).grid(row=0, column=0, sticky="w")
        create_badge(title_row, status, status).grid(row=0, column=1, sticky="e")
        for index, line in enumerate(lines):
            tk.Label(
                card,
                text=line,
                bg=theme.PANEL,
                fg=theme.MUTED,
                font=("Segoe UI", 12),
            ).grid(row=index + 1, column=1, sticky="w", padx=28, pady=(0, 10))

    def _routing_row(self, parent: tk.Widget, row_index: int, route) -> None:
        values = (route.route, route.subject, route.publisher, route.subscriber, route.rate)
        widths = (24, 50, 18, 18, 10)
        for column_index, (value, width) in enumerate(zip(values, widths)):
            tk.Label(
                parent,
                text=value,
                bg=theme.BG,
                fg=theme.TEXT,
                font=("Cascadia Mono", 11),
                width=width,
                anchor="w",
            ).grid(row=row_index * 2 - 1, column=column_index, sticky="w", padx=8, pady=10)
        create_badge(parent, route.status, route.status).grid(
            row=row_index * 2 - 1, column=5, sticky="w", padx=8
        )
        tk.Frame(parent, bg=theme.WHITE_LINE, height=1).grid(
            row=row_index * 2, column=0, columnspan=6, sticky="ew"
        )

    def _asset_row(self, parent: tk.Widget, row_index: int, asset) -> None:
        values = (asset.asset_type, asset.fabricant, asset.modele, asset.puissance, asset.modbus)
        widths = (22, 20, 16, 14, 28)
        for column_index, (value, width) in enumerate(zip(values, widths)):
            tk.Label(
                parent,
                text=value,
                bg=theme.BG,
                fg=theme.TEXT,
                font=("Cascadia Mono", 11),
                width=width,
                anchor="w",
            ).grid(row=row_index * 2 - 1, column=column_index, sticky="w", padx=8, pady=10)
        tk.Frame(parent, bg=theme.WHITE_LINE, height=1).grid(
            row=row_index * 2, column=0, columnspan=5, sticky="ew"
        )
