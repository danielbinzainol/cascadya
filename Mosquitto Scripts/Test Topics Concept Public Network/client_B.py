import paho.mqtt.client as mqtt
import ssl

BROKER = "vm-broker.cascadya.local"
PORT = 8883
MY_TOPIC = "data/client_B"
CLIENT_ID = "Edge_Device_B"

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"✅ {CLIENT_ID} connecté! J'attends mes commandes...")
        client.subscribe(MY_TOPIC)

def on_message(client, userdata, msg):
    print(f"🟠 [CLIENT B] Reçu : {msg.payload.decode()}")

# API v2
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=CLIENT_ID)
client.tls_set(ca_certs="ca.crt", certfile="client.crt", keyfile="client.key", tls_version=ssl.PROTOCOL_TLSv1_2)

client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT, 60)
client.loop_forever()