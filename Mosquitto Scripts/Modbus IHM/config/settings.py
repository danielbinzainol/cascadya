import os
from pathlib import Path

# ==========================================
# 📂 CHEMINS DU PROJET
# ==========================================
# Identifie le dossier racine du projet (steamswitch_ihm)
BASE_DIR = Path(__file__).resolve().parent.parent

# ==========================================
# 🔐 CERTIFICATS TLS
# ==========================================
CERTS_DIR = BASE_DIR / "config" / "certs"

CA_CERT = str(CERTS_DIR / "ca.crt")
CLIENT_CERT = str(CERTS_DIR / "client.crt")
CLIENT_KEY = str(CERTS_DIR / "client.key")

# ==========================================
# 🌐 CONFIGURATION NATS (VM Broker)
# ==========================================
NATS_URL = "tls://10.42.1.6:4222"  # L'IP WireGuard de votre VM Broker

# On prépare déjà les topics pour la scalabilité du projet
TOPIC_PING = "cascadya.routing.ping"             # Pour tester le Watchdog
TOPIC_TELEMETRY = "cascadya.routing.telemetry"   # Pour la lecture continue (Pression, États...)
TOPIC_COMMAND = "cascadya.routing.command"       # Pour écrire les consignes (C1, C2, C3...)

# ==========================================
# ⚙️ REGISTRES MODBUS (SteamSwitch)
# ==========================================
REG_WATCHDOG = 620  # %MW620 (Test de liaison)
# Vous pourrez ajouter les autres registres ici (ex: REG_PRESSION = 400, etc.)

# ==========================================
# 🎨 CONFIGURATION VISUELLE (CustomTkinter)
# ==========================================
APP_TITLE = "SteamSwitch - Centre de Contrôle Edge"
APP_GEOMETRY = "950x650"  # Taille de la fenêtre au lancement
THEME_COLOR = "blue"      # Thème principal (blue, dark-blue, green)
APPEARANCE_MODE = "dark"  # Mode sombre par défaut pour un look industriel
REFRESH_RATE_MS = 100     # Vitesse de rafraîchissement de l'IHM (10 images/seconde)