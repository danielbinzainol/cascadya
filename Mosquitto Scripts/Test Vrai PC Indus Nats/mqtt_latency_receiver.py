import paho.mqtt.client as mqtt
import ssl

# Configuration
MQTT_BROKER = "51.15.64.139" # IP Publique (ou Tailscale si Mosquitto écoute dessus)
PORT = 8883 # Port TLS standard pour MQTT

def on_connect(client, userdata, flags, rc):
    print(f"✅ PC Industriel connecté à Mosquitto (RC: {rc})")
    client.subscribe("cascadya/command/pc_indus")

def on_message(client, userdata, msg):
    # Renvoi immédiat (écho) vers le topic ACK
    client.publish("cascadya/ack/pc_indus", msg.payload)

client = mqtt.Client()

# Configuration mTLS (ajustez les chemins si nécessaire)
client.tls_set(ca_certs="certs/ca.crt", 
               certfile="certs/client.crt", 
               keyfile="certs/client.key")
client.tls_insecure_set(True) # Équivalent à check_hostname = False

client.on_connect = on_connect
client.on_message = on_message

client.connect(MQTT_BROKER, PORT)
client.loop_forever()