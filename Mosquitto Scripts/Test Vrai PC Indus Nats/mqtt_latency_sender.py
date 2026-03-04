import paho.mqtt.client as mqtt
import time
import ssl
import json
import csv
import statistics

# Configuration
MQTT_BROKER = "10.42.1.6" # IP WireGuard
PORT = 8883
TOTAL_MESSAGES = 1000

rtt_results = []
received_count = 0

def on_message(client, userdata, msg):
    global received_count
    receive_ts = time.time()
    payload = json.loads(msg.payload.decode())
    send_ts = payload.get("send_ts")
    if send_ts:
        rtt_results.append((receive_ts - send_ts) * 1000)
        received_count += 1

client = mqtt.Client()
client.tls_set(ca_certs="../ca.crt", certfile="../client.crt", keyfile="../client.key")
client.tls_insecure_set(True)
client.on_message = on_message

client.connect(MQTT_BROKER, PORT)
client.subscribe("cascadya/ack/pc_indus")
client.loop_start()

print(f"🚀 Début du test MQTT ({TOTAL_MESSAGES} pings)...")
start_test_time = time.time()

for i in range(TOTAL_MESSAGES):
    payload = json.dumps({"send_ts": time.time(), "id": i})
    client.publish("cascadya/command/pc_indus", payload)
    time.sleep(0.002) # Même délai que pour NATS

# Attente des derniers retours
time.sleep(5)
client.loop_stop()

# Calcul et export
if rtt_results:
    avg_rtt = statistics.mean(rtt_results)
    jitter = statistics.stdev(rtt_results)
    throughput = received_count / (time.time() - start_test_time - 5)
    
    with open("audit_metrics_mqtt.csv", mode='w', newline='') as file:
        writer = csv.writer(file, delimiter=';')
        writer.writerow(["Metrique", "Valeur", "Unite"])
        writer.writerow(["Protocol", "MQTT", "N/A"])
        writer.writerow(["Messages Reçus", received_count, "msg"])
        writer.writerow(["Latence Moyenne", round(avg_rtt, 2), "ms"])
        writer.writerow(["Jitter", round(jitter, 2), "ms"])
    print("📁 Fichier audit_metrics_mqtt.csv généré.")