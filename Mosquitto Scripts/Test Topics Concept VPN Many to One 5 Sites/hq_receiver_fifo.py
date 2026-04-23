import paho.mqtt.client as mqtt
import json
import os
from datetime import datetime

BROKER_HOST = "mosquitto.cascadya.internal"
BROKER_PORT = 8883
LISTEN_TOPIC = "cascadya/hq/loris"

# Configuration du FIFO
MAX_LINES = 500
LOG_DIR = "logs_sites"

# Création du dossier de logs s'il n'existe pas
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

def update_fifo_file(site_name, log_entry):
    """Gère l'écriture dans le fichier TXT avec la rotation FIFO"""
    filepath = os.path.join(LOG_DIR, f"{site_name}.txt")
    lines = []
    
    # 1. Lire les lignes existantes
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            lines = f.readlines()
            
    # 2. Ajouter la nouvelle ligne
    lines.append(log_entry + "\n")
    
    # 3. Couper pour ne garder que les MAX_LINES dernières (FIFO)
    if len(lines) > MAX_LINES:
        lines = lines[-MAX_LINES:]
        
    # 4. Réécrire le fichier proprement
    with open(filepath, 'w') as f:
        f.writelines(lines)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"✅ Connecté au QG central via WireGuard !")
        print(f"🎧 Écoute et rangement automatique (Max {MAX_LINES} lignes/site)...")
        client.subscribe(LISTEN_TOPIC, qos=1)
    else:
        print(f"❌ Échec de la connexion (Code {rc})")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        
        # Identifier le site
        source_topic = payload.get("source_topic", "Inconnu")
        site_name = source_topic.split("/")[2] if "/" in source_topic else "Site_Inconnu"
        
        # Créer l'entrée de log avec un timestamp propre
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {json.dumps(payload)}"
        
        # Mettre à jour le fichier
        update_fifo_file(site_name, log_entry)
        print(f"💾 Log enregistré pour {site_name}")
        
    except Exception as e:
        print(f"❌ Erreur de traitement : {e}")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="loris-hq-receiver")
client.on_connect = on_connect
client.on_message = on_message

# Chemins des certificats
client.tls_set(ca_certs="../ca.crt", certfile="../client.crt", keyfile="../client.key")

client.connect(BROKER_HOST, BROKER_PORT, 60)
client.loop_forever()