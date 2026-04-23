import paho.mqtt.client as mqtt
import ssl
import json

BROKER_IP = "51.15.64.139"

def on_connect(client, userdata, flags, rc):
    print("✅ Connecté au Broker local via mTLS !")
    print("🎧 En attente d'ordres depuis le Cloud (ThingsBoard)...")
    # Abonnement au topic officiel RPC de ThingsBoard
    client.subscribe("v1/devices/me/rpc/request/+")

def on_subscribe(client, userdata, mid, granted_qos):
    print(f"📡 CONFIRMATION : Le Broker a accepté notre abonnement (QoS: {granted_qos})")

def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode()
    
    print(f"\n🚨 ALERTE : Ordre reçu depuis le Cloud !")
    print(f"➡️ Topic   : {topic}")
    print(f"➡️ Commande: {payload}")
    
    # ThingsBoard ajoute un ID unique à chaque requête (ex: v1/devices/me/rpc/request/42)
    request_id = topic.split('/')[-1]
    
    # --- SIMULATION DE L'ACTION INDUSTRIELLE ---
    try:
        data = json.loads(payload)
        if data.get("method") == "setValve":
            etat = "OUVERTE" if data.get("params") else "FERMÉE"
            print(f"⚙️ Action physique : La vanne est maintenant {etat}.")
    except Exception as e:
        print("Erreur de décodage de la commande.")

    # --- ENVOI DE LA RÉPONSE AU CLOUD ---
    # ThingsBoard attend une réponse pour valider que l'ordre a bien été exécuté
    response = {"status": "SUCCESS", "message": "Ordre exécuté sur WSL"}
    response_topic = f"v1/devices/me/rpc/response/{request_id}"
    
    client.publish(response_topic, json.dumps(response))
    print(f"✅ Accusé de réception envoyé à ThingsBoard.")

# Initialisation (Compatibilité Paho v2)
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="WSL_Actuator")

# Configuration mTLS (On utilise tes certificats générés par Ansible)
client.tls_set(
    ca_certs="../ca.crt", 
    certfile="../client.crt", 
    keyfile="../client.key", 
    tls_version=ssl.PROTOCOL_TLSv1_2
)
client.tls_insecure_set(True)
client.on_subscribe = on_subscribe
client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER_IP, 8883, 60)
client.loop_forever()