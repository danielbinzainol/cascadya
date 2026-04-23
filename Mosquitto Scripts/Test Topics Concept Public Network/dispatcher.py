import paho.mqtt.client as mqtt
import ssl
import json

# Configuration
BROKER = "vm-broker.cascadya.local"
PORT = 8883
INPUT_TOPIC = "cmd/dispatch"
CLIENT_ID = "Server_Dispatcher"

def on_connect(client, userdata, flags, rc):
    print(f"🧠 {CLIENT_ID} en ligne. J'écoute les ordres sur {INPUT_TOPIC}...")
    client.subscribe(INPUT_TOPIC)

def on_message(client, userdata, msg):
    payload_str = msg.payload.decode()
    print(f"⚡ Ordre reçu : {payload_str}")
    
    try:
        # Décortiquer le JSON
        data = json.loads(payload_str)
        
        # Logique de dispatching
        target = data.get("target")
        message = data.get("message")
        
        if target == "A":
            topic_dest = "data/client_A"
            print(f"   ↪ Redirection vers Client A...")
            client.publish(topic_dest, message)
            
        elif target == "B":
            topic_dest = "data/client_B"
            print(f"   ↪ Redirection vers Client B...")
            client.publish(topic_dest, message)
            
        elif target == "ALL":
            print(f"   ↪ Redirection vers TOUS...")
            client.publish("data/client_A", message)
            client.publish("data/client_B", message)
            
        else:
            print(f"   ❌ Cible '{target}' inconnue.")

    except json.JSONDecodeError:
        print("   ❌ Erreur : Le payload n'est pas un JSON valide.")

client = mqtt.Client(client_id=CLIENT_ID)
client.tls_set(ca_certs="ca.crt", certfile="client.crt", keyfile="client.key", tls_version=ssl.PROTOCOL_TLSv1_2)
# client.tls_insecure_set(True)

client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT, 60)
client.loop_forever()