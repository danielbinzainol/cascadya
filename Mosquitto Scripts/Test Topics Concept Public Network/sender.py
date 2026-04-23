import paho.mqtt.client as mqtt
import ssl
import json
import time
import random

# --- CONFIGURATION ---
BROKER = "vm-broker.cascadya.local"
PORT = 8883
TOPIC = "cmd/dispatch"
CLIENT_ID = "Controller_Sequencer"

# Pattern de distribution : 2 pour A, 1 pour B
SEQUENCE_PATTERN = ["A", "A", "B"]

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"✅ {CLIENT_ID} connecté au broker.")
    else:
        print(f"❌ Erreur de connexion : {rc}")

# Initialisation (API v2)
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=CLIENT_ID)

# Sécurité mTLS
client.tls_set(
    ca_certs="ca.crt", 
    certfile="client.crt", 
    keyfile="client.key", 
    tls_version=ssl.PROTOCOL_TLSv1_2
)

# Connexion
client.on_connect = on_connect
client.connect(BROKER, PORT, 60)

# On lance la boucle réseau en arrière-plan pour gérer les messages systèmes
client.loop_start()

# --- BOUCLE D'ENVOI INFINIE ---
try:
    index = 0
    print(f"🚀 Démarrage de la séquence : {SEQUENCE_PATTERN}")
    
    while True:
        # 1. Sélectionner la cible selon le pattern (A, A, B, A, A, B...)
        target = SEQUENCE_PATTERN[index % len(SEQUENCE_PATTERN)]
        
        # 2. Générer un numéro de commande aléatoire
        order_number = random.randint(1000, 9999)
        
        # 3. Créer le Payload
        payload = {
            "target": target,
            "message": f"Commande #{order_number}"
        }
        
        # 4. Publier
        print(f"📤 Envoi de {payload['message']} vers -> [ {target} ]")
        client.publish(TOPIC, json.dumps(payload))
        
        # 5. Attendre 3 secondes
        time.sleep(3)
        
        # Passer au suivant dans la liste
        index += 1

except KeyboardInterrupt:
    print("\n🛑 Arrêt de l'envoi.")
    client.loop_stop()
    client.disconnect()