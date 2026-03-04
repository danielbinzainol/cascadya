import paho.mqtt.client as mqtt
import sys
import json

# Require a client ID when launching the script
if len(sys.argv) < 2:
    print("⚠️ Usage: python universal_client.py <CLIENT_ID> (e.g., A or B)")
    sys.exit(1)

CLIENT_ID = sys.argv[1].upper()
MY_TOPIC = f"cascadya/client/{CLIENT_ID}"

BROKER_HOST = "mosquitto.cascadya.internal"
BROKER_PORT = 8883

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"✅ [Client {CLIENT_ID}] Connected via WireGuard!")
        print(f"🎧 Subscribing to my dedicated topic: {MY_TOPIC}")
        client.subscribe(MY_TOPIC, qos=1)
    else:
        print(f"❌ Connection failed (Code {rc})")

def on_message(client, userdata, msg):
    payload = json.loads(msg.payload.decode())
    print(f"\n[{CLIENT_ID}] 📩 Received routed payload:")
    print(json.dumps(payload, indent=2))

# Fixed API version warning
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=f"wsl-receiver-{CLIENT_ID}")
client.on_connect = on_connect
client.on_message = on_message

# Pointing one folder up (../) to find the certificates
client.tls_set(
    ca_certs="../ca.crt", 
    certfile="../client.crt", 
    keyfile="../client.key"
)

client.connect(BROKER_HOST, BROKER_PORT, 60)
client.loop_forever()