import paho.mqtt.client as mqtt
import json
import ssl

BROKER = "51.15.64.139" # Votre IP Broker Cloud [cite: 131, 141]
PORT = 8883
DEVICE_TOKEN = "PuW9IQkIZ18U1m3nLlIm" # À récupérer dans l'interface ThingsBoard

def on_connect(client, userdata, flags, rc):
    print(f"Connexion résultat : {rc}")
    if rc == 0:
        print("✅ Connecté à ThingsBoard via Traefik !")
        # Envoi d'une donnée de test
        payload = {"temperature": 25.5, "status": "WSL_TEST_OK"}
        client.publish("v1/devices/me/telemetry", json.dumps(payload), qos=1)
        print("📤 Donnée envoyée sur v1/devices/me/telemetry")

client = mqtt.Client()
client.username_pw_set(DEVICE_TOKEN) # Obligatoire pour ThingsBoard
client.on_connect = on_connect

# Configuration TLS (on ignore la validité pour le test)
client.tls_set(cert_reqs=ssl.CERT_NONE)
client.tls_insecure_set(True)

client.connect(BROKER, PORT)
client.loop_forever()