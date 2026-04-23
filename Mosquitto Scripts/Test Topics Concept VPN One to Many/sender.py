import paho.mqtt.client as mqtt
import json
import time
import random

BROKER_HOST = "mosquitto.cascadya.internal"
BROKER_PORT = 8883
INBOX_TOPIC = "cascadya/inbox"

# Fixed API version warning
sender = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="wsl-sender")

# Pointing one folder up (../) to find the certificates
sender.tls_set(
    ca_certs="../ca.crt", 
    certfile="../client.crt", 
    keyfile="../client.key"
)

print(f"🔌 Sender connecting to {BROKER_HOST}...")
sender.connect(BROKER_HOST, BROKER_PORT, 60)
sender.loop_start()

targets = ["A", "B"]

try:
    print("🚀 Starting data generation (Ctrl+C to stop)")
    while True:
        # Pick a random target
        intended_target = random.choice(targets)
        
        # Build the payload
        payload = {
            "target_client": intended_target,
            "temperature": round(random.uniform(20.0, 35.0), 2),
            "humidity": round(random.uniform(40.0, 60.0), 2),
            "status": "OPERATIONAL",
            "source": "WSL_Testing_Suite"
        }
        
        print(f"📤 Sending payload intended for Client {intended_target} to the INBOX...")
        sender.publish(INBOX_TOPIC, json.dumps(payload), qos=1)
        
        time.sleep(3) # Send every 3 seconds

except KeyboardInterrupt:
    print("\n🛑 Stopping sender.")
    sender.loop_stop()
    sender.disconnect()