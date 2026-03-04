import customtkinter as ctk
from config import settings

class DashboardTab(ctk.CTkFrame):
    def __init__(self, master, comms, **kwargs):
        super().__init__(master, **kwargs)
        self.comms = comms

        # Configuration de la grille
        self.grid_columnconfigure((0, 1), weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- SECTION CONTRÔLE (Haut) ---
        self.control_frame = ctk.CTkFrame(self)
        self.control_frame.grid(row=0, column=0, columnspan=2, padx=20, pady=20, sticky="nsew")
        
        self.label_title = ctk.CTkLabel(self.control_frame, text="Contrôle du Watchdog (%MW620)", font=("Arial", 18, "bold"))
        self.label_title.pack(pady=10)

        # Entrée pour la valeur
        self.entry_valeur = ctk.CTkEntry(self.control_frame, placeholder_text="Valeur (ex: 99)", width=150)
        self.entry_valeur.insert(0, "99")
        self.entry_valeur.pack(side="left", padx=(100, 10), pady=20)

        # Bouton d'envoi
        self.btn_send = ctk.CTkButton(self.control_frame, text="🚀 Envoyer au Modbus", 
                                      command=self.on_ping_click, font=("Arial", 14, "bold"))
        self.btn_send.pack(side="left", padx=10, pady=20)

        # --- SECTION AFFICHAGE (Bas) ---
        # Tuile : Valeur Retournée
        self.tile_value = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.tile_value.grid(row=1, column=0, padx=20, pady=20, sticky="nsew")
        
        ctk.CTkLabel(self.tile_value, text="VALEUR RETOURNÉE", font=("Arial", 14, "bold")).pack(pady=10)
        self.display_val = ctk.CTkLabel(self.tile_value, text="---", font=("Arial", 60, "bold"), text_color="#1f538d")
        self.display_val.pack(expand=True)

        # Tuile : État de l'Intégrité
        self.tile_status = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.tile_status.grid(row=1, column=1, padx=20, pady=20, sticky="nsew")
        
        ctk.CTkLabel(self.tile_status, text="INTÉGRITÉ DES DONNÉES", font=("Arial", 14, "bold")).pack(pady=10)
        self.display_status = ctk.CTkLabel(self.tile_status, text="ATTENTE", font=("Arial", 30, "bold"), text_color="gray")
        self.display_status.pack(expand=True)

    def on_ping_click(self):
        """Action au clic sur le bouton"""
        try:
            val = int(self.entry_valeur.get())
            self.display_status.configure(text="EN COURS...", text_color="orange")
            # On envoie la commande au moteur réseau
            self.comms.trigger_ping(val)
        except ValueError:
            self.display_status.configure(text="ERREUR FORMAT", text_color="red")

    def update_ui(self, msg):
        """Mise à jour des widgets quand une réponse NATS arrive"""
        data = msg.get("data", {})
        val_envoyee = msg.get("valeur_envoyee")
        val_recue = data.get("valeur_retour")
        
        # Mise à jour de la valeur
        self.display_val.configure(text=str(val_recue) if val_recue is not None else "---")

        # Vérification de l'intégrité
        if data.get("status") == "ok" and val_envoyee == val_recue:
            self.display_status.configure(text="🟢 VALIDÉE", text_color="green")
        else:
            raison = data.get("message", "ÉCHEC")
            self.display_status.configure(text=f"🔴 {raison}", text_color="red")