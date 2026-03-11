import queue

import customtkinter as ctk

from config import settings
from network.comms_manager import CommsManager
from ui.components.status_bar import StatusBar
from ui.tabs.dashboard import DashboardTab
from ui.tabs.planificateur import PlanificateurTab
from utils.logger import log


class SteamSwitchApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(settings.APP_TITLE)
        self.geometry(settings.APP_GEOMETRY)
        ctk.set_appearance_mode(settings.APPEARANCE_MODE)
        ctk.set_default_color_theme(settings.THEME_COLOR)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.comms = CommsManager()
        self.comms.start()

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, padx=20, pady=(20, 0), sticky="nsew")

        tab_dash = self.tabview.add("Dashboard")
        tab_plan = self.tabview.add("Scheduler")

        self.dashboard = DashboardTab(tab_dash, self.comms)
        self.dashboard.pack(fill="both", expand=True)

        self.planificateur = PlanificateurTab(tab_plan, self.comms)
        self.planificateur.pack(fill="both", expand=True)

        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=1, column=0, padx=20, pady=20, sticky="ew")

        log.info("UI ready. Starting network queue polling.")
        self.check_network_queue()

    def check_network_queue(self):
        try:
            while True:
                msg = self.comms.rx_queue.get_nowait()
                self.process_network_message(msg)
        except queue.Empty:
            pass
        finally:
            self.after(settings.REFRESH_RATE_MS, self.check_network_queue)

    def process_network_message(self, msg):
        msg_type = msg.get("type")

        if msg_type == "nats_status":
            self.status_bar.set_nats_status(bool(msg.get("connected", False)))
            return

        if msg_type == "ping_result":
            data = msg.get("data", {})
            if data.get("status") == "ok":
                self.status_bar.set_nats_status(True)
                self.status_bar.set_modbus_status(True)
                self.status_bar.update_latency(data.get("rtt_ms", 0.0))
            else:
                self.status_bar.set_modbus_status(False)
                log.error(f"Modbus ping error: {data.get('message')}")

            self.dashboard.update_ui(msg)
            return

        if msg_type == "command_result":
            data = msg.get("data", {})
            is_ok = data.get("status") == "ok"
            self.status_bar.set_modbus_status(is_ok)
            self.planificateur.handle_command_result(msg)

    def on_closing(self):
        log.info("Stopping app and network connections...")
        self.comms.stop()
        self.destroy()
