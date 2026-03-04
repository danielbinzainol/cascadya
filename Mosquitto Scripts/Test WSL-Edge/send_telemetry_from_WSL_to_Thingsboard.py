import paho.mqtt.client as mqtt
import json
import time
import random
import ssl

# --- Configuration ---
BROKER_IP = "51.15.64.139"
BROKER_PORT = 8883
TOPIC = "v1/devices/me/telemetry"


# APRES (Il faut remonter d'un dossier avec "..") :
CA_CERT = "../ca.crt"
CLIENT_CERT = "../client.crt"
CLIENT_KEY = "../client.key"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Connecté au Broker via mTLS !")
    else:
        print(f"❌ Échec de connexion, code : {rc}")

# Initialisation du client
client = mqtt.Client(client_id="WSL_Industrial_Sensor")
client.on_connect = on_connect

# Configuration TLS (mTLS)
client.tls_set(
    ca_certs=CA_CERT,
    certfile=CLIENT_CERT,
    keyfile=CLIENT_KEY,
    cert_reqs=ssl.CERT_REQUIRED,
    tls_version=ssl.PROTOCOL_TLSv1_2
)

# Désactivation de la vérification du hostname (utile si votre certificat est lié à l'IP)
client.tls_insecure_set(True)

print(f"Connexion à {BROKER_IP} sur le port {BROKER_PORT}...")
client.connect(BROKER_IP, BROKER_PORT, 60)

client.loop_start()

try:
    while True:
        # Simulation de données
        payload = {
            "temperature": round(random.uniform(20.0, 35.0), 2),
            "humidity": round(random.uniform(40.0, 60.0), 2),
            "status": "OPERATIONAL",
            "source": "WSL_Testing_Suite"
        }
        
        print(f"Envoi : {payload}")
        client.publish(TOPIC, json.dumps(payload), qos=1)
        
        time.sleep(5)  # Envoi toutes les 5 secondes

except KeyboardInterrupt:
    print("\nArrêt du script...")
    client.loop_stop()
    client.disconnect()