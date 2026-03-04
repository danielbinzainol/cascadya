import customtkinter as ctk
import queue
from config import settings
from network.comms_manager import CommsManager
from ui.components.status_bar import StatusBar
from ui.tabs.dashboard import DashboardTab
from ui.tabs.planificateur import PlanificateurTab
from utils.logger import log

class SteamSwitchApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- CONFIGURATION DE LA FENÊTRE ---
        self.title(settings.APP_TITLE)
        self.geometry(settings.APP_GEOMETRY)
        ctk.set_appearance_mode(settings.APPEARANCE_MODE)
        ctk.set_default_color_theme(settings.THEME_COLOR)

        # Gestion de la fermeture propre
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # --- INITIALISATION RÉSEAU ---
        # Le manager lance le thread NATS en arrière-plan
        self.comms = CommsManager()
        self.comms.start()

        # --- MISE EN PAGE (GRID) ---
        self.grid_rowconfigure(0, weight=1)  # Zone principale
        self.grid_columnconfigure(0, weight=1)

        # 1. Système d'onglets (Navigation principale)
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, padx=20, pady=(20, 0), sticky="nsew")
        
        # Création des pages d'onglets
        tab_dash = self.tabview.add("Tableau de Bord")
        tab_plan = self.tabview.add("Planificateur C1/C2/C3")

        # 2. Chargement des composants dans les onglets
        # On passe 'self.comms' pour que les onglets puissent envoyer des commandes
        self.dashboard = DashboardTab(tab_dash, self.comms)
        self.dashboard.pack(fill="both", expand=True)

        self.planificateur = PlanificateurTab(tab_plan, self.comms)
        self.planificateur.pack(fill="both", expand=True)

        # 3. Barre d'état (Status Bar en bas)
        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=1, column=0, padx=20, pady=20, sticky="ew")

        # --- LANCEMENT DU MONITORING ---
        log.info("IHM prête. Démarrage de la boucle de surveillance réseau.")
        self.check_network_queue()

    def check_network_queue(self):
        """
        Vérifie la file d'attente réseau toutes les 100ms.
        C'est ce qui permet de mettre à jour l'IHM sans qu'elle ne freeze.
        """
        try:
            while True:
                # Récupère le message sans attendre (non-bloquant)
                msg = self.comms.rx_queue.get_nowait()
                self.process_network_message(msg)
        except queue.Empty:
            # La file est vide, c'est normal
            pass
        finally:
            # Planifie la prochaine vérification (100ms définis dans settings.py)
            self.after(settings.REFRESH_RATE_MS, self.check_network_queue)

    def process_network_message(self, msg):
        """Analyse le message reçu et met à jour les bons widgets"""
        msg_type = msg.get("type")

        if msg_type == "ping_result":
            data = msg.get("data", {})
            # Mise à jour de la barre d'état (Voyants et Latence)
            if data.get("status") == "ok":
                self.status_bar.set_nats_status(True)
                self.status_bar.set_modbus_status(True)
                self.status_bar.update_latency(data.get("rtt_ms", 0.0))
            else:
                self.status_bar.set_modbus_status(False)
                log.error(f"Erreur Modbus reçue : {data.get('message')}")

            # Mise à jour visuelle du Dashboard (Valeur retournée)
            self.dashboard.update_ui(msg)

    def on_closing(self):
        """Procédure d'arrêt sécurisée"""
        log.info("Arrêt de l'application et des connexions...")
        self.comms.stop() # Arrête le thread NATS
        self.destroy()    # Détruit la fenêtre