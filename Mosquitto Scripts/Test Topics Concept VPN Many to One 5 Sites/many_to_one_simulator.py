import paho.mqtt.client as mqtt
import json
import time
import random
import threading

BROKER_HOST = "mosquitto.cascadya.internal"
BROKER_PORT = 8883

def simulate_site(site_id):
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=f"wsl-site-{site_id}")
    client.tls_set(ca_certs="../ca.crt", certfile="../client.crt", keyfile="../client.key")
    
    client.connect(BROKER_HOST, BROKER_PORT, 60)
    client.loop_start()
    
    topic = f"cascadya/site/{site_id}/telemetry"
    
    print(f"🏭 {site_id} démarré. Envoi sur {topic}")
    
    try:
        while True:
            payload = {
                "site": site_id,
                "production_rate": round(random.uniform(80.0, 100.0), 2),
                "errors": random.randint(0, 2),
                "timestamp": time.time()
            }
            client.publish(topic, json.dumps(payload), qos=1)
            # Chaque site envoie des données à un intervalle aléatoire (entre 2 et 5 secondes)
            time.sleep(random.uniform(2.0, 5.0))
    except KeyboardInterrupt:
        client.loop_stop()
        client.disconnect()

# Lancer 5 sites en parallèle grâce aux threads
sites = ["Site_Alpha", "Site_Beta", "Site_Gamma", "Site_Delta", "Site_Omega"]
threads = []

print("🚀 Démarrage de la simulation des 5 sites industriels...")
for site in sites:
    t = threading.Thread(target=simulate_site, args=(site,))
    t.daemon = True
    t.start()
    threads.append(t)

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n🛑 Arrêt de tous les sites.")