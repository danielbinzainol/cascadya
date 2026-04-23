import paho.mqtt.client as mqtt
import json


BROKER_HOST = "mosquitto.cascadya.internal"
BROKER_PORT = 8883
INBOX_TOPIC = "cascadya/inbox"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"⚙️ Dispatcher active. Listening to {INBOX_TOPIC}...")
        client.subscribe(INBOX_TOPIC, qos=1)

def on_message(client, userdata, msg):
    try:
        # Read the incoming generic message
        raw_data = msg.payload.decode()
        payload = json.loads(raw_data)

        # Determine the final address from the payload
        target = payload.get("target_client")

        if target:
            # Construct the final specific topic
            final_topic = f"cascadya/client/{target}"
            print(f"🔀 Dispatching message to -> {final_topic}")

            # Forward the payload to the specific client
            client.publish(final_topic, raw_data, qos=1)
        else:
            print("⚠️ Message dropped: No 'target_client' specified in payload.")

    except Exception as e:
        print(f"❌ Routing error: {e}")

dispatcher = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="broker-dispatcher")
dispatcher.on_connect = on_connect
dispatcher.on_message = on_message

dispatcher.tls_set(
    ca_certs="/home/ubuntu/ca.crt",
    certfile="/home/ubuntu/server.crt",
    keyfile="/home/ubuntu/server.key"
)

dispatcher.tls_insecure_set(True)
dispatcher.connect(BROKER_HOST, BROKER_PORT, 60)
dispatcher.loop_forever()