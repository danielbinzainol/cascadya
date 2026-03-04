import customtkinter as ctk
from ui.app import SteamSwitchApp
from utils.logger import log

def main():
    log.info("Lancement de l'IHM SteamSwitch...")
    
    # Initialisation de l'application
    app = SteamSwitchApp()
    
    try:
        # Boucle principale (bloquante)
        app.mainloop()
    except KeyboardInterrupt:
        log.warning("Interruption manuelle détectée.")
    finally:
        log.info("Application fermée proprement.")

if __name__ == "__main__":
    main()