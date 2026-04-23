import paho.mqtt.client as mqtt
import json

BROKER_HOST = "127.0.0.1" # Il tourne sur la VM, donc localhost
BROKER_PORT = 8883

# Le "+" permet d'écouter les sites 1, 2, 3, 4, 5... d'un seul coup !
LISTEN_TOPIC = "cascadya/site/+/telemetry" 
TARGET_HQ_TOPIC = "cascadya/hq/loris"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"⚙️ Dispatcher RETOUR actif. Écoute sur {LISTEN_TOPIC}...")
        client.subscribe(LISTEN_TOPIC, qos=1)

def on_message(client, userdata, msg):
    try:
        # Extraire l'ID du site depuis le topic (ex: cascadya/site/Site_3/telemetry)
        site_id = msg.topic.split("/")[2]
        
        raw_data = msg.payload.decode()
        payload = json.loads(raw_data)
        
        # On peut enrichir la donnée en ajoutant la provenance si elle n'y est pas
        payload["routed_by"] = "VM_Return_Dispatcher"
        payload["source_topic"] = msg.topic

        print(f"📥 Donnée reçue du {site_id} -> Transfert vers le QG (Loris)")
        
        # On renvoie tout vers le topic centralisé de Loris
        client.publish(TARGET_HQ_TOPIC, json.dumps(payload), qos=1)

    except Exception as e:
        print(f"❌ Erreur de routage retour: {e}")

dispatcher = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="broker-dispatch-return")
dispatcher.on_connect = on_connect
dispatcher.on_message = on_message

dispatcher.tls_set(ca_certs="/home/ubuntu/ca.crt", certfile="/home/ubuntu/server.crt", keyfile="/home/ubuntu/server.key")
dispatcher.tls_insecure_set(True)

dispatcher.connect(BROKER_HOST, BROKER_PORT, 60)
dispatcher.loop_forever()