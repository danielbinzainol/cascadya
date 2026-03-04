import paho.mqtt.client as mqtt
import json

# --- CONFIGURATION ---
MQTT_BROKER = "10.42.1.6"  # On remplace NATS_URL par MQTT_BROKER (IP WireGuard)
NODE_ID = "WSL_CLIENT" 
CA_CERT = "../ca.crt"
CLIENT_CERT = "../client.crt"
CLIENT_KEY = "../client.key"

def on_connect(client, userdata, flags, rc):
    print(f"✅ {NODE_ID} prêt pour l'audit MQTT One-to-Many...")
    client.subscribe("audit/ping/broadcast")

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        data["node_id"] = NODE_ID
        # On renvoie l'ACK sur un topic spécifique au nœud
        client.publish(f"audit/ack/{NODE_ID}", json.dumps(data))
    except Exception as e:
        print(f"Erreur traitement message: {e}")

client = mqtt.Client()
client.tls_set(ca_certs=CA_CERT, certfile=CLIENT_CERT, keyfile=CLIENT_KEY)
client.tls_insecure_set(True)
client.on_connect = on_connect
client.on_message = on_message

client.connect(MQTT_BROKER, 8883)
client.loop_forever()