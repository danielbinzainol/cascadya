import customtkinter as ctk
import time
from config import settings

class PlanificateurTab(ctk.CTkFrame):
    def __init__(self, master, comms, **kwargs):
        super().__init__(master, **kwargs)
        self.comms = comms

        self.grid_columnconfigure((0, 1, 2), weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- TITRE ---
        self.title = ctk.CTkLabel(self, text="PLANIFICATEUR D'ORDRES STEAMSWITCH", 
                                  font=("Arial", 20, "bold"))
        self.title.grid(row=0, column=0, columnspan=3, pady=30)

        # --- BOUTONS DE SCÉNARIOS (Réf: Note Technique Page 5 & 9) ---
        # Scénario 1 : Priorité Électrique (C1: Production 5.3B, C2: Attente 180°C, C3: Repli)
        self.btn_prio_elec = ctk.CTkButton(self, text="SCÉNARIO :\nPRIORITÉ ÉLEC", height=100, 
                                           fg_color="#1e8449", hover_color="#196f3d", font=("Arial", 16, "bold"),
                                           command=self.send_prio_elec)
        self.btn_prio_elec.grid(row=1, column=0, padx=20, pady=20, sticky="nsew")

        # Scénario 2 : Appoint (Exemple Page 9)
        self.btn_appoint = ctk.CTkButton(self, text="SCÉNARIO :\nAPPOINT", height=100, 
                                         fg_color="#1f538d", hover_color="#1a4575", font=("Arial", 16, "bold"),
                                         command=self.send_appoint)
        self.btn_appoint.grid(row=1, column=1, padx=20, pady=20, sticky="nsew")

        # Scénario 3 : Repli / Arrêt (Consigne dégradée forcée)
        self.btn_repli = ctk.CTkButton(self, text="SCÉNARIO :\nREPLI SÉCURITÉ", height=100, 
                                       fg_color="#922b21", hover_color="#7b241c", font=("Arial", 16, "bold"),
                                       command=self.send_repli)
        self.btn_repli.grid(row=1, column=2, padx=20, pady=20, sticky="nsew")

        # --- LOG DE COMMANDE ---
        self.log_box = ctk.CTkTextbox(self, height=200, font=("Courier New", 12))
        self.log_box.grid(row=2, column=0, columnspan=3, padx=20, pady=20, sticky="nsew")
        self.log_message("Système prêt. En attente de planification d'ordre...")

    # =========================================================
    # LOGIQUE DES SCÉNARIOS (Mapping vers Note Technique)
    # =========================================================

    def send_prio_elec(self):
        """Scénario type : Priorité Électrique (Réf Page 5/9)"""
        # C1 (Principale) : Attributs {3; 400kW; 5.3}
        # C2 (Attente)    : Attributs {5; 180; 0}
        # C3 (Dégradée)   : Attributs {0; 0; 0}
        order = {
            "id": int(time.time()),
            "c1": [3, 400, 53], # 53 pour 5.3 Bar (Modbus INT)
            "c2": [5, 180, 0],
            "c3": [0, 0, 0]
        }
        self.execute_order("PRIORITÉ ÉLEC", order)

    def send_appoint(self):
        """Scénario type : Appoint (Réf Page 9)"""
        order = {
            "id": int(time.time()),
            "c1": [1, 200, 53], 
            "c2": [5, 120, 0],
            "c3": [0, 0, 0]
        }
        self.execute_order("APPOINT", order)

    def send_repli(self):
        """Scénario type : Repli / Arrêt (Réf Page 5)"""
        order = {
            "id": int(time.time()),
            "c1": [0, 0, 0], 
            "c2": [0, 0, 0],
            "c3": [0, 0, 0] # False / Nul
        }
        self.execute_order("REPLI SÉCURITÉ", order)

    def execute_order(self, label, payload):
        """Envoie l'ordre structuré vers NATS via le comms_manager"""
        self.log_message(f"▶️ Envoi Scénario {label}...")
        self.log_message(f"   ID: {payload['id']} | C1: {payload['c1']}")
        
        # Appel de la méthode de comms_manager
        self.comms.send_command(settings.TOPIC_COMMAND, payload)

    def log_message(self, text):
        self.log_box.insert("end", f"[{time.strftime('%H:%M:%S')}] {text}\n")
        self.log_box.see("end")