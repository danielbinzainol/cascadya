import customtkinter as ctk


class DashboardTab(ctk.CTkFrame):
    def __init__(self, master, comms, **kwargs):
        super().__init__(master, **kwargs)
        self.comms = comms

        self.grid_columnconfigure((0, 1), weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.control_frame = ctk.CTkFrame(self)
        self.control_frame.grid(row=0, column=0, columnspan=2, padx=20, pady=20, sticky="nsew")

        self.label_title = ctk.CTkLabel(
            self.control_frame,
            text="Watchdog Ping (%MW620)",
            font=("Arial", 18, "bold"),
        )
        self.label_title.pack(pady=10)

        self.entry_value = ctk.CTkEntry(self.control_frame, placeholder_text="Value (ex: 99)", width=150)
        self.entry_value.insert(0, "99")
        self.entry_value.pack(side="left", padx=(100, 10), pady=20)

        self.btn_send = ctk.CTkButton(
            self.control_frame,
            text="Send Ping",
            command=self.on_ping_click,
            font=("Arial", 14, "bold"),
        )
        self.btn_send.pack(side="left", padx=10, pady=20)

        self.tile_value = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.tile_value.grid(row=1, column=0, padx=20, pady=20, sticky="nsew")

        ctk.CTkLabel(self.tile_value, text="RETURNED VALUE", font=("Arial", 14, "bold")).pack(pady=10)
        self.display_val = ctk.CTkLabel(self.tile_value, text="---", font=("Arial", 60, "bold"), text_color="#1f538d")
        self.display_val.pack(expand=True)

        self.tile_status = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.tile_status.grid(row=1, column=1, padx=20, pady=20, sticky="nsew")

        ctk.CTkLabel(self.tile_status, text="DATA INTEGRITY", font=("Arial", 14, "bold")).pack(pady=10)
        self.display_status = ctk.CTkLabel(self.tile_status, text="WAITING", font=("Arial", 30, "bold"), text_color="gray")
        self.display_status.pack(expand=True)

    def on_ping_click(self):
        try:
            value = int(self.entry_value.get())
            self.display_status.configure(text="RUNNING...", text_color="orange")
            self.comms.trigger_ping(value)
        except ValueError:
            self.display_status.configure(text="BAD INPUT", text_color="red")

    def update_ui(self, msg):
        data = msg.get("data", {})
        value_sent = msg.get("value_sent", msg.get("valeur_envoyee"))
        value_returned = data.get("valeur_retour")

        self.display_val.configure(text=str(value_returned) if value_returned is not None else "---")

        if data.get("status") == "ok" and value_sent == value_returned:
            self.display_status.configure(text="VALID", text_color="green")
        else:
            reason = data.get("message", "FAILED")
            self.display_status.configure(text=f"ERROR: {reason}", text_color="red")
