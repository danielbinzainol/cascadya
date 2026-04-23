from __future__ import annotations

import tkinter as tk

from ui import theme
from ui.widgets import ScrollableFrame, create_badge, metric_card


class DashboardPage(tk.Frame):
    def __init__(self, master: tk.Misc, app: "ControlPlaneApp") -> None:
        super().__init__(master, bg=theme.BG)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.scroll = ScrollableFrame(self)
        self.scroll.grid(row=0, column=0, sticky="nsew")
        self.content = self.scroll.content
        self.content.grid_columnconfigure(0, weight=1)

        self.metric_specs: tuple[tuple[str, str], ...] = ()
        self.metric_widgets: list[tk.Frame] = []
        self.site_widgets: list[tk.Widget] = []
        self._build()

    def _build(self) -> None:
        header = tk.Frame(self.content, bg=theme.BG)
        header.grid(row=0, column=0, sticky="ew", pady=(6, 18))
        header.grid_columnconfigure(0, weight=1)

        tk.Label(
            header,
            text="Cascadya control plane",
            bg=theme.BG,
            fg=theme.TEXT,
            font=("Segoe UI Semibold", 22),
        ).grid(row=0, column=0, sticky="w")

        tk.Button(
            header,
            text="+ Provisionner un site",
            command=lambda: self.app.show_provisioning("laiterie-bretagne"),
            bg=theme.BG,
            fg=theme.TEXT,
            activebackground="#141414",
            activeforeground=theme.TEXT,
            relief="solid",
            bd=1,
            padx=20,
            pady=10,
            font=("Segoe UI Semibold", 12),
            cursor="hand2",
        ).grid(row=0, column=1, sticky="e")

        metrics = tk.Frame(self.content, bg=theme.BG)
        metrics.grid(row=1, column=0, sticky="ew", pady=(0, 28))
        for index in range(4):
            metrics.grid_columnconfigure(index, weight=1)

        self.metric_specs = (
            ("Sites actifs", "_metric_sites_active"),
            ("ems-site healthy", "_metric_ems_site_health"),
            ("Routes ok", "_metric_routes"),
            ("Capacite aFRR totale", "_metric_capacity"),
        )
        for index, (title, _) in enumerate(self.metric_specs):
            widget = metric_card(metrics, title, "-", "-")
            widget.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 12, 0))
            self.metric_widgets.append(widget)

        tk.Label(
            self.content,
            text="Services centraux",
            bg=theme.BG,
            fg=theme.TEXT,
            font=("Segoe UI Semibold", 18),
        ).grid(row=2, column=0, sticky="w", pady=(0, 18))

        services = tk.Frame(self.content, bg=theme.BG)
        services.grid(row=3, column=0, sticky="ew", pady=(0, 34))
        services.grid_columnconfigure(0, weight=1)
        services.grid_columnconfigure(1, weight=1)

        self._service_card(
            services,
            0,
            "ems-core",
            "healthy",
            ("Config v43 synced", "Gere 12 sites", "Dernier heartbeat il y a 12s"),
        )
        self._service_card(
            services,
            1,
            "ems-light",
            "healthy",
            ("Config v18 synced", "IEC 104 active - RTE connected", "Dernier heartbeat il y a 8s"),
        )

        tk.Label(
            self.content,
            text="Sites",
            bg=theme.BG,
            fg=theme.TEXT,
            font=("Segoe UI Semibold", 18),
        ).grid(row=4, column=0, sticky="w", pady=(0, 16))

        table = tk.Frame(self.content, bg=theme.BG)
        table.grid(row=5, column=0, sticky="ew")
        self.table = table
        self._configure_table_columns()

        headers = ("Site", "Statut", "ems-site", "Routes", "Capacite", "Dernier HB")
        for index, label in enumerate(headers):
            tk.Label(
                table,
                text=label,
                bg=theme.BG,
                fg=theme.MUTED,
                font=("Segoe UI Semibold", 11),
            ).grid(row=0, column=index, sticky="w", padx=(24, 12), pady=(0, 12))

        self.refresh()

    def _configure_table_columns(self) -> None:
        widths = (360, 180, 180, 300, 160, 140)
        weights = (3, 1, 1, 2, 1, 1)
        for index, (width, weight) in enumerate(zip(widths, weights)):
            self.table.grid_columnconfigure(index, minsize=width, weight=weight, uniform="sites")

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
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 12, 0))
        card.grid_columnconfigure(0, weight=1)

        title_row = tk.Frame(card, bg=theme.PANEL)
        title_row.grid(row=0, column=0, sticky="ew", padx=22, pady=(22, 10))
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
            ).grid(row=index + 1, column=0, sticky="w", padx=22, pady=(0, 8))

    def refresh(self) -> None:
        self._refresh_metrics()
        for widget in self.site_widgets:
            widget.destroy()
        self.site_widgets.clear()

        for row_index, site in enumerate(self.app.state.sites.values(), start=1):
            grid_row = row_index * 2 - 1
            widgets = self._site_row(grid_row, site)
            self.site_widgets.extend(widgets)

            separator = tk.Frame(self.table, bg=theme.WHITE_LINE, height=1)
            separator.grid(row=grid_row + 1, column=0, columnspan=6, sticky="ew")
            self.site_widgets.append(separator)

    def _site_row(self, grid_row: int, site) -> list[tk.Widget]:
        created: list[tk.Widget] = []

        site_button = tk.Label(
            self.table,
            text=f"{site.name}\n{site.city} ({site.code})",
            bg=theme.BG,
            fg=theme.TEXT,
            justify="left",
            font=("Segoe UI Semibold", 13),
        )
        site_button.grid(row=grid_row, column=0, sticky="w", padx=(24, 12), pady=16)
        self._bind_open(site_button, site.site_id)
        created.append(site_button)

        status_badge = create_badge(self.table, site.status, site.status)
        status_badge.grid(row=grid_row, column=1, sticky="w", padx=(24, 12))
        self._bind_open(status_badge, site.site_id)
        created.append(status_badge)

        ems_badge = create_badge(self.table, site.ems_site_status, site.ems_site_status)
        ems_badge.grid(row=grid_row, column=2, sticky="w", padx=(24, 12))
        self._bind_open(ems_badge, site.site_id)
        created.append(ems_badge)

        route_frame = tk.Frame(self.table, bg=theme.BG)
        route_frame.grid(row=grid_row, column=3, sticky="w", padx=(24, 12))
        self._route_meter(
            route_frame,
            site.site_id,
            site.routes_ok,
            site.routes_total,
            site.ems_site_status,
        )
        self._bind_open(route_frame, site.site_id)
        created.append(route_frame)

        capacity = tk.Label(
            self.table,
            text=f"{site.capacity_mw:.1f} MW",
            bg=theme.BG,
            fg=theme.TEXT,
            font=("Segoe UI Semibold", 13),
        )
        capacity.grid(row=grid_row, column=4, sticky="w", padx=(24, 12))
        self._bind_open(capacity, site.site_id)
        created.append(capacity)

        heartbeat = tk.Label(
            self.table,
            text=site.last_hb,
            bg=theme.BG,
            fg=theme.MUTED,
            font=("Cascadia Mono", 11),
        )
        heartbeat.grid(row=grid_row, column=5, sticky="w", padx=(24, 12))
        self._bind_open(heartbeat, site.site_id)
        created.append(heartbeat)

        return created

    def _refresh_metrics(self) -> None:
        for widget, (_, method_name) in zip(self.metric_widgets, self.metric_specs):
            value, subtitle = getattr(self, method_name)()
            labels = [child for child in widget.winfo_children() if isinstance(child, tk.Label)]
            if len(labels) >= 3:
                labels[1].configure(text=value)
                labels[2].configure(text=subtitle)

    def _metric_sites_active(self) -> tuple[str, str]:
        active = sum(1 for site in self.app.state.sites.values() if site.status == "active")
        provisioning = sum(
            1 for site in self.app.state.sites.values() if site.status == "provisioning"
        )
        return str(active), f"{provisioning} en provisioning"

    def _metric_ems_site_health(self) -> tuple[str, str]:
        healthy = sum(
            1 for site in self.app.state.sites.values() if site.ems_site_status == "healthy"
        )
        total = len(self.app.state.sites)
        degraded = sum(
            1 for site in self.app.state.sites.values() if site.ems_site_status == "degraded"
        )
        return f"{healthy} / {total}", f"{degraded} degraded"

    def _metric_routes(self) -> tuple[str, str]:
        routes_ok = sum(site.routes_ok for site in self.app.state.sites.values())
        routes_total = sum(site.routes_total for site in self.app.state.sites.values())
        degraded = sum(
            1 for site in self.app.state.sites.values() if site.routes_ok < site.routes_total
        )
        return f"{routes_ok} / {routes_total}", f"{degraded} degraded"

    def _metric_capacity(self) -> tuple[str, str]:
        total_capacity = sum(site.capacity_mw for site in self.app.state.sites.values())
        total_sites = len(self.app.state.sites)
        return f"{total_capacity:.1f} MW", f"{total_sites} sites"

    def _route_meter(
        self,
        parent: tk.Widget,
        site_id: str,
        ok_count: int,
        total_count: int,
        tone: str,
    ) -> None:
        bar = tk.Canvas(parent, width=120, height=12, bg=theme.BG, highlightthickness=0, bd=0)
        bar.grid(row=0, column=0, sticky="w")
        bar.create_rectangle(0, 0, 120, 12, fill="#d8d4ca", width=0)
        width = 0 if total_count == 0 else 120 * (ok_count / total_count)
        fill = theme.GREEN if tone == "healthy" else (theme.AMBER if tone == "degraded" else "#ece6d7")
        bar.create_rectangle(0, 0, width, 12, fill=fill, width=0)
        count = tk.Label(
            parent,
            text=f"{ok_count}/{total_count}",
            bg=theme.BG,
            fg=theme.TEXT,
            font=("Segoe UI Semibold", 12),
        )
        count.grid(row=0, column=1, sticky="w", padx=(12, 0))
        self._bind_open(bar, site_id)
        self._bind_open(count, site_id)

    def _bind_open(self, widget: tk.Widget, site_id: str) -> None:
        widget.bind("<Button-1>", lambda _event, current=site_id: self._open_site(current))
        widget.configure(cursor="hand2")

    def _open_site(self, site_id: str) -> None:
        if site_id == "laiterie-bretagne":
            self.app.show_provisioning(site_id)
        else:
            self.app.show_site(site_id)
