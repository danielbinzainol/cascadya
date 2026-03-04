import paho.mqtt.client as mqtt
import time
import json
import statistics
import csv

MQTT_BROKER = "10.42.1.6" # IP WireGuard
TOTAL_PINGS = 1000
EXPECTED_NODES = ["PC_INDUS", "WSL_CLIENT"]
results = {node: [] for node in EXPECTED_NODES}

def on_message(client, userdata, msg):
    receive_ts = time.time()
    data = json.loads(msg.payload.decode())
    node_id = data.get("node_id")
    send_ts = data.get("send_ts")
    if node_id in results:
        results[node_id].append((receive_ts - send_ts) * 1000)

client = mqtt.Client()
client.tls_set(ca_certs="../ca.crt", certfile="../client.crt", keyfile="../client.key")
client.tls_insecure_set(True)
client.on_message = on_message

client.connect(MQTT_BROKER, 8883)
for node in EXPECTED_NODES:
    client.subscribe(f"audit/ack/{node}")
client.loop_start()

print(f"🚀 Diffusion MQTT de {TOTAL_PINGS} pings...")
for i in range(TOTAL_PINGS):
    payload = {"send_ts": time.time(), "id": i}
    client.publish("audit/ping/broadcast", json.dumps(payload))
    time.sleep(0.01)

time.sleep(3)
client.loop_stop()

# Export et Affichage
print("\n📊 RÉSULTATS MQTT ONE-TO-MANY")
for node, rtts in results.items():
    avg = statistics.mean(rtts) if rtts else 0
    print(f"Node: {node:12} | RTT Moyen: {avg:.2f}ms | Reçus: {len(rtts)}")