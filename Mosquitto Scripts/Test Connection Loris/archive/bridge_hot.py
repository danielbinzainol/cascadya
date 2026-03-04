import ssl
import json
import time
import statistics
import requests
import paho.mqtt.client as mqtt
from collections import defaultdict

# =========================
# MQTT
# =========================
BROKER = "vm-broker.cascadya.local"
PORT = 8883

CA_FILE = "/opt/vernemq/ssl/ca-chain.crt"
CERT_FILE = "/opt/vernemq/ssl/broker.crt"
KEY_FILE = "/opt/vernemq/ssl/broker.key"

HOT_TOPIC = "telemetry/+/hot/meas"

# =========================
# ThingsBoard
# =========================
TB_HOST = "https://thingsboard-dev.cascadya.com"

TB_TOKENS = {
    "site-001": "PuW9IQkIZ18U1m3nLlIm"
}

# =========================
# Aggregation
# =========================
WINDOW = defaultdict(list)
WINDOW_START = defaultdict(lambda: int(time.time() // 60))


def send_to_thingsboard(site_id: str, data: dict):
    token = TB_TOKENS.get(site_id)
    if not token:
        print(f"⚠️ No ThingsBoard token for {site_id}")
        return

    url = f"{TB_HOST}/api/v1/{token}/telemetry"
    try:
        r = requests.post(url, json=data, timeout=2)
        r.raise_for_status()
        print(f"📤 Sent to TB {site_id} → {data}")
    except Exception as e:
        print(f"❌ TB error {site_id} → {e}")


def on_connect(client, userdata, flags, rc):
    print("✅ Bridge connected", rc)
    client.subscribe(HOT_TOPIC)

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        site_id = msg.topic.split("/")[1]
        p_kw = float(payload["p_fast_kw"])
    except Exception as e:
        print("❌ Invalid HOT payload:", e)
        return

    minute = int(time.time() // 60)

    if minute != WINDOW_START[site_id]:
        values = WINDOW[site_id]
        if values:
            agg = {
                "ts": minute * 60,
                "avg_kw": statistics.mean(values),
                "min_kw": min(values),
                "max_kw": max(values),
            }

            print(f"[TB AGG] {site_id} → {agg}")
            send_to_thingsboard(site_id, agg)

        WINDOW[site_id].clear()
        WINDOW_START[site_id] = minute

    WINDOW[site_id].append(p_kw)

client = mqtt.Client(client_id="bridge-hot")
client.tls_set(
    ca_certs=CA_FILE,
    certfile=CERT_FILE,
    keyfile=KEY_FILE,
    tls_version=ssl.PROTOCOL_TLS_CLIENT,
)

client.on_connect = on_connect
client.on_message = on_message

print("🚀 Starting HOT → ThingsBoard bridge")
client.connect(BROKER, PORT)
client.loop_forever()