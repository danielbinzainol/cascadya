import paho.mqtt.client as mqtt
import json
import time

# Configuration
BROKER_HOST = "mosquitto.cascadya.internal"
BROKER_PORT = 8883
TOPIC = "cascadya/site-001/command/setpoint"

# Les certificats doivent être dans le même dossier que ce script
CA_CERT = "ca.crt"
CLIENT_CERT = "client.crt"
CLIENT_KEY = "client.key"

# Callbacks pour voir ce qu'il se passe
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Connecté au Broker avec succès (mTLS validé) !")
        
        # Le payload JSON demandé par Luc
        payload = {
            "power_kw": 500, 
            "timestamp": "2026-02-27T10:00:00Z"
        }
        
        # Envoi du message
        print(f"📤 Envoi de la commande sur {TOPIC}...")
        client.publish(TOPIC, json.dumps(payload), qos=1)
        print("✅ Message envoyé !")
        
    else:
        print(f"❌ Échec de connexion. Code d'erreur : {rc}")

# Initialisation du client (paho-mqtt v1.x)
client = mqtt.Client(client_id="cmarket-loris-test")
client.on_connect = on_connect

# Configuration du mTLS
print("🔒 Chargement des certificats...")
client.tls_set(
    ca_certs=CA_CERT,
    certfile=CLIENT_CERT,
    keyfile=CLIENT_KEY
)

# Connexion
print(f"🌐 Connexion à {BROKER_HOST} via le VPN...")
try:
    client.connect(BROKER_HOST, BROKER_PORT, 60)
    # Laisse le script tourner quelques secondes pour traiter l'envoi
    client.loop_start()
    time.sleep(3)
    client.loop_stop()
    client.disconnect()
except Exception as e:
    print(f"❌ Erreur réseau : {e}")