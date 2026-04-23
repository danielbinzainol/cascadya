import paho.mqtt.client as mqtt
import json

BROKER_HOST = "mosquitto.cascadya.internal"
BROKER_PORT = 8883
LISTEN_TOPIC = "cascadya/hq/loris" # L'entonnoir central !

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"✅ Connecté au QG central via WireGuard !")
        print(f"🎧 Écoute du flux agrégé sur : {LISTEN_TOPIC}")
        client.subscribe(LISTEN_TOPIC, qos=1)
    else:
        print(f"❌ Échec de la connexion (Code {rc})")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        
        # On extrait le nom du site depuis le topic d'origine que le dispatcher a gentiment ajouté
        source_topic = payload.get("source_topic", "Inconnu")
        site_name = source_topic.split("/")[2] if "/" in source_topic else "Inconnu"

        print(f"\n🏭 [FLUX RETOUR - {site_name}] 📊 Données reçues :")
        print(json.dumps(payload, indent=2))
        print("-" * 50)
        
    except Exception as e:
        print(f"❌ Erreur de lecture : {e}")

# Utilisation de VERSION1 pour rester cohérent avec tes autres scripts
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="loris-hq-receiver")
client.on_connect = on_connect
client.on_message = on_message

# On remonte d'un dossier pour trouver les certificats clients de Loris
client.tls_set(
    ca_certs="../ca.crt", 
    certfile="../client.crt", 
    keyfile="../client.key"
)

print(f"🔌 Tentative de connexion à {BROKER_HOST}...")
client.connect(BROKER_HOST, BROKER_PORT, 60)
client.loop_forever()