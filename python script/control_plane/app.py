from __future__ import annotations

import tkinter as tk

from data import build_mock_state
from ui import theme
from ui.pages.dashboard_page import DashboardPage
from ui.pages.e2e_page import E2EPage
from ui.pages.provisioning_page import ProvisioningPage
from ui.pages.site_page import SitePage


class ControlPlaneApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(theme.APP_TITLE)
        self.geometry(theme.APP_GEOMETRY)
        self.minsize(*theme.MIN_WINDOW_SIZE)
        self.configure(bg=theme.BG)
        self.state = build_mock_state()

        self.container = tk.Frame(self, bg=theme.BG)
        self.container.pack(fill="both", expand=True, padx=24, pady=18)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.pages = {
            "dashboard": DashboardPage(self.container, self),
            "site": SitePage(self.container, self),
            "e2e": E2EPage(self.container, self),
            "provisioning": ProvisioningPage(self.container, self),
        }
        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")

        self.show_dashboard()

    def show_dashboard(self) -> None:
        self.pages["dashboard"].refresh()
        self.pages["dashboard"].tkraise()

    def show_site(self, site_id: str) -> None:
        page: SitePage = self.pages["site"]  # type: ignore[assignment]
        page.set_site(site_id)
        page.tkraise()

    def show_e2e(self, site_id: str) -> None:
        page: E2EPage = self.pages["e2e"]  # type: ignore[assignment]
        page.set_site(site_id)
        page.tkraise()

    def show_provisioning(self, site_id: str) -> None:
        page: ProvisioningPage = self.pages["provisioning"]  # type: ignore[assignment]
        page.set_site(site_id)
        page.tkraise()

    def on_provisioning_event(self, site_id: str, event: str) -> None:
        site = self.state.sites[site_id]
        if event == "started":
            site.status = "provisioning"
            site.ems_site_status = "waiting"
            site.routes_ok = 0
            site.last_hb = "---"
            site.last_job_summary = "Provisioning in progress"
        elif event == "awaiting_reboot":
            site.status = "provisioning"
            site.ems_site_status = "waiting"
            site.last_job_summary = "9/11 steps done - waiting for reboot proof"
        elif event == "completed":
            site.status = "active"
            site.ems_site_status = "healthy"
            site.routes_ok = site.routes_total
            site.last_hb = "just now"
            site.last_job_summary = "11/11 provisioning proof complete"
        elif event == "failed":
            site.status = "provisioning"
            site.ems_site_status = "degraded"
            site.last_job_summary = "Provisioning failed - review job log"
