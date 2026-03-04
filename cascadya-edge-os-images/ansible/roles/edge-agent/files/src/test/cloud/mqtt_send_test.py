import time
import json
import ssl
import random
import paho.mqtt.client as mqtt

#BROKER = "vm-broker.cascadya.local"
BROKER = "51.15.64.139"
PORT = 8883

# Les topics
TOPIC = "cmd/site-001/setpoint"               # Pour envoyer les ordres
ACK_TOPIC = "status/site-001/setpoint_ack"    # Pour écouter les confirmations

# Chemins des certificats
CA_CERT = "../../certs/ca-chain.crt"
CLIENT_CERT = "../../certs/client.crt"
CLIENT_KEY = "../../certs/client.key"

# --- NOUVEAU : Le Publisher devient aussi Subscriber ---

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"📡 Connecté ! En écoute des confirmations sur : {ACK_TOPIC}")
        # On s'abonne au topic des réponses
        client.subscribe(ACK_TOPIC, qos=1)

def on_message(client, userdata, msg):
    # Cette fonction se déclenche quand un ACK revient de la machine
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        seq_ack = payload.get("seq_ack")
        status = payload.get("status")
        latence_aller = payload.get("latency_aller_ms")
        
        # Affichage en vert pour bien le voir dans la console
        print(f"   🟢 [CONFIRMATION REÇUE] La machine a appliqué la seq={seq_ack} (Statut: {status}, Latence aller: {latence_aller}ms)")
    except Exception as e:
        print(f"Erreur de lecture de l'ACK : {e}")

# -------------------------------------------------------

client = mqtt.Client(
    client_id="cloud_publisher_001",
    callback_api_version=mqtt.CallbackAPIVersion.VERSION1
)

# On attache nos nouvelles fonctions "d'écoute"
client.on_connect = on_connect
client.on_message = on_message

client.tls_set(
    ca_certs=CA_CERT,
    certfile=CLIENT_CERT,
    keyfile=CLIENT_KEY,
    #cert_reqs=ssl.CERT_REQUIRED,
    cert_reqs=ssl.CERT_NONE,
    tls_version=ssl.PROTOCOL_TLSv1_2
)
client.tls_insecure_set(True)

client.connect(BROKER, PORT)
client.loop_start() # Le thread en arrière-plan va maintenant gérer l'envoi ET la réception

seq = 0

try:
    while True:
        seq += 1
        now = time.time()
        
        # Pour tester votre logique de seuil (> 5kW), on génère une puissance aléatoire
        puissance = round(random.uniform(20.0, 40.0), 1)

        payload = {
            "seq": seq,
            "p_kw": puissance,
            "valid_to": int(now + 60),
            "ts_send": now
        }

        print(f"📤 [ENVOI seq={seq}] Ordre envoyé : {puissance} kW")
        client.publish(TOPIC, json.dumps(payload), qos=1)
        
        time.sleep(2) # Ralenti à 2 secondes pour vous laisser le temps de lire

except KeyboardInterrupt:
    client.loop_stop()
    client.disconnect()