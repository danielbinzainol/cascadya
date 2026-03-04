import time
import json
import ssl
import paho.mqtt.client as mqtt

#BROKER = "vm-broker.cascadya.local"
BROKER = "51.15.64.139"
PORT = 8883

# Les topics
CMD_TOPIC = "cmd/site-001/setpoint"       # Ce qu'on écoute (les ordres du cloud)
ACK_TOPIC = "status/site-001/setpoint_ack" # Ce qu'on répond (les confirmations)

# Chemins absolus vers les certificats (pour le test en local sur WSL)
CA_CERT = "../../certs/ca-chain.crt"
CLIENT_CERT = "../../certs/client.crt"
CLIENT_KEY = "../../certs/client.key"

# Variables pour simuler votre logique de fréquence de réponse
message_count = 0
last_applied_p_kw = 0.0

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"✅ Connecté au broker avec succès ! En écoute sur : {CMD_TOPIC}")
        client.subscribe(CMD_TOPIC, qos=1)
    else:
        print(f"❌ Échec de la connexion. Code: {rc}")

def on_message(client, userdata, msg):
    global message_count, last_applied_p_kw
    now = time.time()
    message_count += 1
    
    try:
        # Décoder le message JSON reçu
        payload = json.loads(msg.payload.decode("utf-8"))
        ts_send = payload.get("ts_send", now)
        new_p_kw = payload.get("p_kw", 0.0)
        seq = payload.get("seq", 0)
        
        # 1. Calcul de la latence "Aller" (Cloud -> Edge)
        latency_ms = (now - ts_send) * 1000
        print(f"\n📥 [REÇU seq={seq}] Consigne: {new_p_kw}kW | Latence trajet: {latency_ms:.2f} ms")

        # 2. Votre logique métier (Doit-on envoyer un ACK ?)
        # Exemple : On envoie un ACK si la différence est de plus de 5kW OU tous les 3 messages
        diff = abs(new_p_kw - last_applied_p_kw)
        
        if diff >= 5.0 or message_count % 3 == 0:
            print(f"   ⚙️  Application de la nouvelle consigne ({new_p_kw}kW)...")
            last_applied_p_kw = new_p_kw
            
            # Préparation de l'Accusé de Réception (ACK)
            ack_payload = {
                "seq_ack": seq,             # On cite le numéro de séquence auquel on répond
                "status": "APPLIED",
                "current_p_kw": new_p_kw,
                "latency_aller_ms": round(latency_ms, 2),
                "ts_ack": time.time()       # Heure d'envoi de la confirmation
            }
            
            # 3. Envoi de la réponse vers le Cloud
            client.publish(ACK_TOPIC, json.dumps(ack_payload), qos=1)
            print(f"   📤 [ACK ENVOYÉ] Topic: {ACK_TOPIC}")
        else:
            print("   💤 Changement mineur, la machine ignore/n'envoie pas d'ACK pour économiser la data.")

    except Exception as e:
        print(f"Erreur de traitement du message: {e}")

# Initialisation du client
client = mqtt.Client(
    client_id="edge_receiver_001",
    callback_api_version=mqtt.CallbackAPIVersion.VERSION1
)

# Configuration des callbacks
client.on_connect = on_connect
client.on_message = on_message

# Configuration mTLS
client.tls_set(
    ca_certs=CA_CERT,
    certfile=CLIENT_CERT,
    keyfile=CLIENT_KEY,
    #cert_reqs=ssl.CERT_REQUIRED,
    cert_reqs=ssl.CERT_NONE,
    tls_version=ssl.PROTOCOL_TLSv1_2
)
client.tls_insecure_set(True)

print("Connexion au broker...")
client.connect(BROKER, PORT)

try:
    # loop_forever() bloque le script ici et gère la réception en continu
    client.loop_forever()
except KeyboardInterrupt:
    print("\nArrêt du récepteur.")
    client.disconnect()