import customtkinter as ctk

class StatusBar(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, height=40, corner_radius=10, **kwargs)
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)

        # Voyant NATS (Broker)
        self.nats_label = ctk.CTkLabel(self, text="🔴 Broker NATS : Déconnecté", text_color="red", font=("Arial", 14, "bold"))
        self.nats_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        # Voyant Modbus (Simulateur)
        self.modbus_label = ctk.CTkLabel(self, text="🔴 Modbus : Inconnu", text_color="orange", font=("Arial", 14, "bold"))
        self.modbus_label.grid(row=0, column=1, padx=10, pady=10)

        # Jauge de Latence
        self.latency_label = ctk.CTkLabel(self, text="⚡ Latence RTT : --- ms", font=("Arial", 14))
        self.latency_label.grid(row=0, column=2, padx=10, pady=10, sticky="e")

    def set_nats_status(self, connected: bool):
        if connected:
            self.nats_label.configure(text="🟢 Broker NATS : Connecté", text_color="green")
        else:
            self.nats_label.configure(text="🔴 Broker NATS : Déconnecté", text_color="red")

    def set_modbus_status(self, connected: bool):
        if connected:
            self.modbus_label.configure(text="🟢 Modbus Edge : OK", text_color="green")
        else:
            self.modbus_label.configure(text="🔴 Modbus Edge : ERREUR", text_color="red")

    def update_latency(self, rtt_ms: float):
        self.latency_label.configure(text=f"⚡ Latence RTT : {rtt_ms:.1f} ms")