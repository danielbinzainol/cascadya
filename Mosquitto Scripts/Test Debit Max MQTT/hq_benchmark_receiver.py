import paho.mqtt.client as mqtt
import time
import threading

BROKER_HOST = "mosquitto.cascadya.internal"
BROKER_PORT = 8883
LISTEN_TOPIC = "cascadya/hq/loris"

msg_count = 0
running = True

def monitor_throughput():
    """Affiche le nombre de messages reçus chaque seconde"""
    global msg_count
    while running:
        time.sleep(1)
        print(f"📊 Débit actuel : {msg_count} messages/seconde")
        msg_count = 0 # Remise à zéro pour la seconde suivante

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("✅ Connecté au Broker pour le Stress Test !")
        # QoS 0 pour la performance maximale
        client.subscribe(LISTEN_TOPIC, qos=0)
    else:
        print(f"❌ Erreur de connexion {rc}")

def on_message(client, userdata, msg):
    global msg_count
    msg_count += 1 # On incrémente juste le compteur, ultra rapide !

# Utilisation de la VERSION2 pour éviter les DeprecationWarnings
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="loris-benchmark")
client.tls_set(ca_certs="../ca.crt", certfile="../client.crt", keyfile="../client.key")
client.on_connect = on_connect
client.on_message = on_message

# Démarrage du thread d'affichage en arrière-plan
t = threading.Thread(target=monitor_throughput)
t.start()

try:
    client.connect(BROKER_HOST, BROKER_PORT, 60)
    client.loop_forever()
except KeyboardInterrupt:
    print("\n🛑 Fin du test.")
    running = False
    client.disconnect()