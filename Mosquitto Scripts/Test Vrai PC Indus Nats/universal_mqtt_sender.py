import paho.mqtt.client as mqtt
import time

# --- CONFIGURATION ---
MQTT_BROKER = "10.42.1.6"
PORT = 8883
NODE_NAME = "EMETTEUR_MQTT"
TOPIC = "cascadya/routing/test"

CA_CERT = "ca.crt"
CLIENT_CERT = "client.crt"
CLIENT_KEY = "client.key"
# ---------------------

client = mqtt.Client()
client.tls_set(ca_certs=CA_CERT, certfile=CLIENT_CERT, keyfile=CLIENT_KEY)
client.tls_insecure_set(True)

client.connect(MQTT_BROKER, PORT)
client.loop_start()

print(f"✅ [{NODE_NAME}] Connecté ! Prêt à diffuser...")

for i in range(1, 6):
    payload = f"Message #{i} en provenance de {NODE_NAME}"
    client.publish(TOPIC, payload)
    print(f"📤 [{NODE_NAME}] Publié : {payload}")
    time.sleep(1)

client.loop_stop()