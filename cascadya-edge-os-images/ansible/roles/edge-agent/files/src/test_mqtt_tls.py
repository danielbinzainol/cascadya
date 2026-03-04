import ssl
import paho.mqtt.client as mqtt

BROKER = "vm-broker.cascadya.local"
PORT = 8883
TOPIC = "test/tls"

client = mqtt.Client(client_id="edge-test", protocol=mqtt.MQTTv311)

client.tls_set(
    ca_certs="cascadya-ca-chain.crt",
    certfile="device-fullchain.crt",
    keyfile="device.key",
    tls_version=ssl.PROTOCOL_TLSv1_2
)

client.tls_insecure_set(False)

def on_connect(client, userdata, flags, rc):
    print("on_connect rc =", rc)
    if rc == 0:
        client.publish(TOPIC, "TLS OK from paho-mqtt")
        print("PUBLISH SENT")
    else:
        print("CONNECTION FAILED")

def on_disconnect(client, userdata, rc):
    print("DISCONNECTED rc =", rc)

client.on_connect = on_connect
client.on_disconnect = on_disconnect

print("Connecting...")
client.connect(BROKER, PORT, keepalive=60)
client.loop_forever()
