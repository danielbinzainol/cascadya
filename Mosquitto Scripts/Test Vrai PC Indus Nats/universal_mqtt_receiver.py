import paho.mqtt.client as mqtt

# --- CONFIGURATION ---
MQTT_BROKER = "10.42.1.6" # IP WireGuard ou 51.15.64.139 / 100.103.71.126
PORT = 8883
NODE_NAME = "RECEPTEUR_MQTT"
TOPIC = "cascadya/routing/test"

CA_CERT = "ca.crt"
CLIENT_CERT = "client.crt"
CLIENT_KEY = "client.key"
# ---------------------

def on_connect(client, userdata, flags, rc):
    print(f"✅ [{NODE_NAME}] Connecté à Mosquitto ! Écoute sur '{TOPIC}'...")
    client.subscribe(TOPIC)

def on_message(client, userdata, msg):
    print(f"📥 [{NODE_NAME}] Reçu : {msg.payload.decode()}")

client = mqtt.Client()
client.tls_set(ca_certs=CA_CERT, certfile=CLIENT_CERT, keyfile=CLIENT_KEY)
client.tls_insecure_set(True)

client.on_connect = on_connect
client.on_message = on_message

try:
    client.connect(MQTT_BROKER, PORT)
    client.loop_forever()
except KeyboardInterrupt:
    print("\n🛑 Fin de l'écoute.")