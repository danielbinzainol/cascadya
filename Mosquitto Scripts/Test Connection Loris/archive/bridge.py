import ssl
import json
import paho.mqtt.client as mqtt

BROKER = "vm-broker.cascadya.local"
PORT = 8883

CA_FILE = "/opt/vernemq/ssl/ca-chain.crt"
CERT_FILE = "/opt/vernemq/ssl/broker.crt"
KEY_FILE = "/opt/vernemq/ssl/broker.key"

TOPIC = "telemetry/+/hot/#"

def on_connect(client, userdata, flags, rc):
    print("✅ Connected to MQTT with code", rc)
    client.subscribe(TOPIC)

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        print(f"[MQTT] {msg.topic} → {payload}")
    except Exception as e:
        print("❌ Error parsing message:", e)

client = mqtt.Client(client_id="bridge-test")

client.tls_set(
    ca_certs=CA_FILE,
    certfile=CERT_FILE,
    keyfile=KEY_FILE,
    tls_version=ssl.PROTOCOL_TLS_CLIENT,
)

client.on_connect = on_connect
client.on_message = on_message

print("🚀 Starting bridge...")
client.connect(BROKER, PORT)
client.loop_forever()